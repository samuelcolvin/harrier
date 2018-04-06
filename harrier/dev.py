import asyncio
import contextlib
import signal
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import time

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from watchgod import awatch

from .assets import start_webpack_watch, copy_assets, run_grablib
from .build import build_som, render
from .common import Config, logger

HOST = '0.0.0.0'
BUILD_START = 'start'


class Server:
    def __init__(self, config: Config, port: int):
        self.config = config
        self.port = port
        self.loop = asyncio.get_event_loop()
        self.runner = None

    async def start(self):
        app, *_ = serve_static(static_path=str(self.config.dist_dir), livereload=False, port=self.port)
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


class SiteUpdater:
    def __init__(self, config: Config):
        self.config = config
        self.som = {}

    def __call__(self, pages, assets, sass, templates, start):
        if not any([pages, assets, sass, templates]):
            logger.info('no changes to site, not rebuilding')
            return
        if pages == BUILD_START:
            logger.info('building...')
            finish_prefix = ''
        else:
            msg = [
                pages and f'{len(pages)} pages changed',
                assets and 'assets changed',
                sass and 'sass changed',
                templates and 'templates changed'
            ]
            logger.info('%s rebuilding...', ', '.join([m for m in msg if m]))
            finish_prefix = 're'

        if assets:
            copy_assets(self.config)
        if pages or not self.som:
            self.som = build_som(self.config)
        if pages or templates:
            render(self.config, self.som)
        if sass:
            run_grablib(self.config)
        logger.info('%sbuild completed in %0.3fs', finish_prefix, time() - start)


def is_within(location: Path, directory: Path):
    try:
        location.relative_to(directory)
    except ValueError:
        return False
    else:
        return True


async def adev(config: Config, port: int):
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    webpack_process = await start_webpack_watch(config)
    updater = SiteUpdater(config)

    with ProcessPoolExecutor() as executor:
        loop.set_default_executor(executor)
        await loop.run_in_executor(None, updater, BUILD_START, True, True, True, time())

        logger.info('\nStarting dev server start, go to http://localhost:%s', port)
        server = Server(config, port)
        await server.start()

        try:
            async for changes in awatch(config.source_dir, stop_event=stop_event):
                logger.info('file changes: %s', changes)
                start = time()
                pages, assets, sass, templates = set(), False, False, False
                for change, location in changes:
                    location = Path(location)
                    if is_within(location, config.pages_dir):
                        pages.add(location)
                    elif is_within(location, config.theme_dir / 'assets'):
                        assets = True
                    elif is_within(location, config.theme_dir / 'sass'):
                        sass = True
                    elif is_within(location, config.theme_dir / 'templates'):
                        templates = True
                await loop.run_in_executor(None, updater, pages, assets, sass, templates, start)
        finally:
            if webpack_process:
                if webpack_process.returncode is None:
                    webpack_process.send_signal(signal.SIGTERM)
                elif webpack_process.returncode > 0:
                    logger.warning('webpack existed badly, returncode: %d', webpack_process.returncode)
            await server.shutdown()
