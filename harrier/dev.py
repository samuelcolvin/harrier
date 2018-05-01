import asyncio
import contextlib
import logging
import signal
import traceback
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from time import time

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from pydantic import BaseModel
from watchgod import Change, DefaultWatcher, awatch

from .assets import copy_assets, get_path_lookup, run_grablib, start_webpack_watch
from .build import BuildPages, build_pages, content_templates, render_pages
from .common import HarrierProblem, log_complete
from .config import Config, get_config
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


class UpdateArgs(BaseModel):
    config_path: str
    pages: set = FIRST_BUILD
    assets: bool = False
    sass: bool = False
    templates: bool = False
    extensions: bool = False
    update_config: bool = False

    def build_required(self):
        return any([self.pages, self.assets, self.sass, self.templates, self.extensions, self.update_config])


def update_site(args: UpdateArgs):  # noqa: C901 (ignore complexity)
    global CONFIG, SOM
    assert CONFIG, 'CONFIG global not set'
    start_time = time()
    full_build = SOM is None
    first_build = args.pages == FIRST_BUILD
    if first_build:
        logger.info('building...')
        args.assets = args.sass = args.templates = args.extensions = full_build = True
    else:
        msg = [
            args.pages and f'{len(args.pages)} pages changed',
            args.assets and 'assets changed',
            args.sass and 'sass changed',
            args.templates and 'templates changed',
            args.extensions and 'extensions changed',
            args.update_config and 'config changed',
        ]
        logger.info('%s rebuilding...', ', '.join([m for m in msg if m]))

    log_prefix = '' if first_build else 're'
    try:
        if args.update_config:
            CONFIG = get_config(args.config_path)
            args.assets = args.sass = args.templates = args.extensions = full_build = True

        if args.extensions:
            CONFIG.extensions.load()
            config = apply_modifiers(CONFIG, CONFIG.extensions.config_modifiers)
            args.assets = args.sass = args.templates = full_build = True
        else:
            config = CONFIG
        config.build_time = datetime.utcnow()
        if args.assets:
            copy_assets(config)
            args.templates = True  # force re-render as pages might have changed
            args.sass = True  # in case paths changed as used by resolve_url in sass
        if args.sass:
            run_grablib(config)
            args.templates = True  # force re-render as pages might have changed

        if full_build:
            pages = build_pages(config)
            SOM = dict(
                pages=pages,
                data=load_data(config),
                config=config,
                **config.dict(),
            )
            SOM = apply_modifiers(SOM, config.extensions.som_modifiers)
            content_templates(SOM['pages'].values(), config)
        elif args.pages:
            start = time()
            page_builder = BuildPages(config)
            tmp_dir = config.get_tmp_dir()
            to_update = set()
            for change, path in args.pages:
                rel_path = str(path.relative_to(config.pages_dir))
                if change == Change.deleted:
                    page = SOM['pages'][rel_path]
                    page['outfile'].unlink()
                    if 'content_template' in page:
                        (tmp_dir / page['content_template']).unlink()
                    SOM['pages'].pop(rel_path)
                else:
                    SOM['pages'][rel_path] = page_builder.prep_file(path)
                    to_update.add(rel_path)

            SOM = apply_modifiers(SOM, config.extensions.som_modifiers)
            content_templates([SOM['pages'][k] for k in SOM['pages'] if k in to_update], config)
            log_complete(start, 'pages built', len(args.pages))
            args.templates = args.templates or any(change != Change.deleted for change, _ in args.pages)

        SOM['path_lookup'] = get_path_lookup(config, SOM['pages'])
        if args.templates:
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

    config_path = str(config.config_path or config.source_dir)
    # max_workers = 1 so the same config and som are always used to build the site
    with ProcessPoolExecutor(max_workers=1) as executor:
        ret = await loop.run_in_executor(executor, update_site, UpdateArgs(config_path=config_path))

        logger.info('\nStarting dev server, go to http://localhost:%s', port)
        server = Server(config, port)
        await server.start()

        try:
            async for changes in awatch(config.source_dir, stop_event=stop_event, watcher_cls=HarrierWatcher):
                logger.debug('file changes: %s', changes)
                args = UpdateArgs(config_path=config_path, pages=set())
                for change, raw_path in changes:
                    path = Path(raw_path)
                    if is_within(path, config.pages_dir):
                        args.pages.add((change, path))
                    elif is_within(path, config.theme_dir / 'assets'):
                        args.assets = True
                    elif is_within(path, config.theme_dir / 'sass'):
                        args.sass = True
                    elif is_within(path, config.theme_dir / 'templates'):
                        args.templates = True
                    elif path == config.extensions.path:
                        args.extensions = True
                    elif path == config.config_path:
                        args.update_config = True

                if args.build_required():
                    ret = await loop.run_in_executor(executor, update_site, args)
        finally:
            if webpack_process:
                if webpack_process.returncode is None:
                    webpack_process.send_signal(signal.SIGTERM)
                elif webpack_process.returncode > 0:
                    logger.warning('webpack existed badly, returncode: %d', webpack_process.returncode)
            await server.shutdown()
        return ret
