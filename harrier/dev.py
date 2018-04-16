import asyncio
import contextlib
import logging
import signal
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import time

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from watchgod import Change, DefaultWatcher, awatch

from .assets import copy_assets, find_theme_files, run_grablib, start_webpack_watch
from .build import BuildPages, build_pages, render_pages
from .common import HarrierProblem
from .config import Config
from .data import load_data
from .extensions import apply_modifiers

HOST = '0.0.0.0'
logger = logging.getLogger('harrier.dev')


class Server:
    def __init__(self, config: Config, port: int):
        self.config = config
        self.port = port
        self.loop = asyncio.get_event_loop()
        self.runner = None

    async def start(self):
        app, *_ = serve_static(static_path=str(self.config.dist_dir), port=self.port)
        self.runner = AppRunner(app, access_log=None)
        await self.runner.setup()

        site = TCPSite(self.runner, HOST, self.port, shutdown_timeout=0.01)
        await site.start()

    async def shutdown(self):
        logger.info('shutting down server...')
        start = self.loop.time()
        with contextlib.suppress(asyncio.TimeoutError, KeyboardInterrupt):
            await self.runner.cleanup()
        logger.debug('shutdown took %0.2fs', self.loop.time() - start)


# CONFIG will be set before the fork so it can be used by the child process
CONFIG: Config = None
# SOM and BUILD_CACHE will only be set after the fork in the child process created by ProcessPoolExecutor
SOM = None
BUILD_CACHE = {}
FIRST_BUILD = '__FB__'


def update_site(pages, assets, sass, templates, extensions):  # noqa: C901 (ignore complexity)
    assert CONFIG, 'CONFIG global not set'
    start_time = time()
    global SOM
    full_build = SOM is None
    first_build = pages == FIRST_BUILD
    if first_build:
        logger.info('building...')
        full_build = True
    else:
        msg = [
            pages and f'{len(pages)} pages changed',
            assets and 'assets changed',
            sass and 'sass changed',
            templates and 'templates changed'
        ]
        logger.info('%s rebuilding...', ', '.join([m for m in msg if m]))

    log_prefix = '' if first_build else 're'
    try:
        if extensions:
            CONFIG.extensions.load()
            config = apply_modifiers(CONFIG, CONFIG.extensions.config_modifiers)
            assets = sass = templates = full_build = True
        else:
            config = CONFIG

        if assets:
            copy_assets(config)
            templates = True  # force re-render as pages might have changed
            sass = True  # in case paths changed as used by resolve_url in sass
        if sass:
            run_grablib(config)
            templates = True  # force re-render as pages might have changed

        if full_build:
            SOM = config.dict()
            SOM.update(
                theme_files=find_theme_files(config),
                pages=build_pages(config),
                data=load_data(config),
            )
            SOM = apply_modifiers(SOM, config.extensions.som_modifiers)
        elif pages:
            page_builder = BuildPages(config)
            for change, path in pages:
                rel_path = str(path.relative_to(config.pages_dir))
                if change == Change.deleted:
                    SOM['pages'][rel_path]['outfile'].unlink()
                    SOM['pages'].pop(rel_path)
                else:
                    SOM['pages'][rel_path] = page_builder.prep_file(path)
            SOM = apply_modifiers(SOM, config.extensions.som_modifiers)
            templates = templates or any(change != Change.deleted for change, _ in pages)

        if assets or sass:
            SOM['theme_files'] = find_theme_files(config)

        if templates:
            global BUILD_CACHE
            BUILD_CACHE = render_pages(config, SOM)
    except HarrierProblem as e:
        logger.debug('error during build %s %s %s', traceback.format_exc(), e.__class__.__name__, e)
        logger.warning('%sbuild failed in %0.3fs', log_prefix, time() - start_time)
        return 1
    else:
        logger.info('%sbuild completed in %0.3fs', log_prefix, time() - start_time)
        return 0


def is_within(location: Path, directory: Path):
    try:
        location.relative_to(directory)
    except ValueError:
        return False
    else:
        return True


class HarrierWatcher(DefaultWatcher):
    def __init__(self, root_path):
        self._used_paths = str(CONFIG.pages_dir), str(CONFIG.theme_dir)
        super().__init__(root_path)

    def should_watch_dir(self, entry):
        return super().should_watch_dir(entry) and entry.path.startswith(self._used_paths)


async def adev(config: Config, port: int):
    global CONFIG
    CONFIG = config
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    webpack_process = await start_webpack_watch(config)

    # max_workers = 1 so the same config and som are always used to build the site
    with ProcessPoolExecutor(max_workers=1) as executor:
        ret = await loop.run_in_executor(executor, update_site, FIRST_BUILD, True, True, True, True)

        logger.info('\nStarting dev server, go to http://localhost:%s', port)
        server = Server(config, port)
        await server.start()

        try:
            async for changes in awatch(config.source_dir, stop_event=stop_event, watcher_cls=HarrierWatcher):
                logger.debug('file changes: %s', changes)
                pages, assets, sass, templates, extensions = set(), False, False, False, False
                for change, raw_path in changes:
                    path = Path(raw_path)
                    if is_within(path, config.pages_dir):
                        pages.add((change, path))
                    elif is_within(path, config.theme_dir / 'assets'):
                        assets = True
                    elif is_within(path, config.theme_dir / 'sass'):
                        sass = True
                    elif is_within(path, config.theme_dir / 'templates'):
                        templates = True
                    elif path == config.extensions.path:
                        extensions = True

                if any([pages, assets, sass, templates, extensions]):
                    ret = await loop.run_in_executor(executor, update_site, pages, assets, sass, templates, extensions)
        finally:
            if webpack_process:
                if webpack_process.returncode is None:
                    webpack_process.send_signal(signal.SIGTERM)
                elif webpack_process.returncode > 0:
                    logger.warning('webpack existed badly, returncode: %d', webpack_process.returncode)
            await server.shutdown()
        return ret
