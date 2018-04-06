import asyncio
import contextlib
import signal

from aiohttp.web_runner import AppRunner, TCPSite
from aiohttp_devtools.runserver import serve_static
from watchgod import awatch

from .assets import start_webpack_watch
from .common import Config, logger

HOST = '0.0.0.0'


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


async def update_site(config: Config):
    pass


async def adev(config: Config, port: int):
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    webpack_process = await start_webpack_watch(config)

    logger.info('\nStarting dev server start, go to http://localhost:%s', port)
    server = Server(config, port)
    await server.start()

    try:
        async for changes in awatch(config.source_dir, stop_event=stop_event):
            print(changes)
    finally:
        if webpack_process and webpack_process.returncode is None:
            webpack_process.send_signal(signal.SIGTERM)
        await server.shutdown()
    # try:
    #     async for changes in awatch(config.source_dir):
    #         print(changes)
    # except KeyboardInterrupt:  # pragma: no branch
    #     pass
    # finally:
    #     await server.shutdown()
