import asyncio
import contextlib
import logging
import signal
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import time

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from watchgod import Change, awatch

from .assets import copy_assets, find_theme_files, run_grablib, start_webpack_watch
from .build import BuildPages, build_pages, render_pages
from .config import Config
from .data import load_data
from .extensions import apply_modifiers

HOST = '0.0.0.0'
FIRST_BUILD = '__FB__'
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


def update_site(pages, assets, sass, templates):
    assert CONFIG, 'CONFIG global not set'
    start_time = time()
    first_build = pages == FIRST_BUILD
    if first_build:
        logger.info('building...')
    else:
        msg = [
            pages and f'{len(pages)} pages changed',
            assets and 'assets changed',
            sass and 'sass changed',
            templates and 'templates changed'
        ]
        logger.info('%s rebuilding...', ', '.join([m for m in msg if m]))

    if assets:
        copy_assets(CONFIG)
    if sass:
        run_grablib(CONFIG)

    global SOM
    if first_build or not SOM:
        SOM = CONFIG.dict()
        SOM.update(
            theme_files=find_theme_files(CONFIG),
            pages=build_pages(CONFIG),
            data=load_data(CONFIG),
        )
        SOM = apply_modifiers(SOM, CONFIG.extensions.som_modifiers)
    elif pages:
        page_builder = BuildPages(CONFIG)
        for change, path in pages:
            rel_path = str(path.relative_to(CONFIG.pages_dir))
            if change == Change.deleted:
                SOM['pages'][rel_path]['outfile'].unlink()
                SOM['pages'].pop(rel_path)
            else:
                SOM['pages'][rel_path] = page_builder.prep_file(path)
        SOM = apply_modifiers(SOM, CONFIG.extensions.som_modifiers)

    if assets or sass:
        SOM['theme_files'] = find_theme_files(CONFIG)

    if templates or first_build or any(change != Change.deleted for change, _ in pages):
        global BUILD_CACHE
        BUILD_CACHE = render_pages(CONFIG, SOM, BUILD_CACHE)

    logger.info('%sbuild completed in %0.3fs', '' if first_build else 're', time() - start_time)


def is_within(location: Path, directory: Path):
    try:
        location.relative_to(directory)
    except ValueError:
        return False
    else:
        return True


async def adev(config: Config, port: int):
    config = apply_modifiers(config, config.extensions.config_modifiers)
    global CONFIG
    CONFIG = config
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    webpack_process = await start_webpack_watch(config)

    # max_workers = 1 so the same config and som are always used to build the site
    with ProcessPoolExecutor(max_workers=1) as executor:
        await loop.run_in_executor(executor, update_site, FIRST_BUILD, True, True, True)

        logger.info('\nStarting dev server, go to http://localhost:%s', port)
        server = Server(config, port)
        await server.start()

        try:
            async for changes in awatch(config.source_dir, stop_event=stop_event):
                logger.debug('file changes: %s', changes)
                pages, assets, sass, templates = set(), False, False, False
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

                if any([pages, assets, sass, templates]):
                    await loop.run_in_executor(executor, update_site, pages, assets, sass, templates)
        finally:
            if webpack_process:
                if webpack_process.returncode is None:
                    webpack_process.send_signal(signal.SIGTERM)
                elif webpack_process.returncode > 0:
                    logger.warning('webpack existed badly, returncode: %d', webpack_process.returncode)
            await server.shutdown()
