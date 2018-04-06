import asyncio
import contextlib
import signal
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import time

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from watchgod import Change, awatch

from .assets import start_webpack_watch, copy_assets, run_grablib
from .build import BuildSOM, build_som, render
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


def update_site(config, som, pages, assets, sass, templates):
    if not any([pages, assets, sass, templates]):
        logger.debug('no changes to site, not rebuilding')
        return
    start_time = time()
    is_start = pages == BUILD_START
    if is_start:
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
        copy_assets(config)

    if is_start or not som:
        som = build_som(config)
    elif pages:
        som_builder = BuildSOM(config)
        for change, path in pages:
            obj = som['pages']
            for item in str(path.relative_to(config.pages_dir)).split('/')[:-1]:
                obj = obj[item]
            if change == Change.deleted:
                obj[path.name]['outfile'].unlink()
                obj.pop(path.name)
            else:
                obj[path.name] = som_builder.prep_file(path)

    if templates or is_start or any(change != Change.deleted for change, _ in pages):
        render(config, som)

    if sass:
        run_grablib(config)
    logger.info('%sbuild completed in %0.3fs', '' if is_start else 're', time() - start_time)
    return som


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

    with ProcessPoolExecutor() as executor:
        loop.set_default_executor(executor)
        som = await loop.run_in_executor(None, update_site, config, None, BUILD_START, True, True, True)

        logger.info('\nStarting dev server, go to http://localhost:%s', port)
        server = Server(config, port)
        await server.start()

        try:
            async for changes in awatch(config.source_dir, stop_event=stop_event):
                logger.debug('file changes: %s', changes)
                pages, assets, sass, templates = set(), False, False, False
                for change, path in changes:
                    path = Path(path)
                    if is_within(path, config.pages_dir):
                        pages.add((change, path))
                    elif is_within(path, config.theme_dir / 'assets'):
                        assets = True
                    elif is_within(path, config.theme_dir / 'sass'):
                        sass = True
                    elif is_within(path, config.theme_dir / 'templates'):
                        templates = True
                som = await loop.run_in_executor(None, update_site, config, som, pages, assets, sass, templates)
        finally:
            if webpack_process:
                if webpack_process.returncode is None:
                    webpack_process.send_signal(signal.SIGTERM)
                elif webpack_process.returncode > 0:
                    logger.warning('webpack existed badly, returncode: %d', webpack_process.returncode)
            await server.shutdown()
