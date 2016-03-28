import asyncio

import pytest
import socket

import aiohttp
from harrier.serve import create_app


def pytest_pycollect_makeitem(collector, name, obj):
    if collector.funcnamefilter(name) and callable(obj):
        return list(collector._genfunctions(name, obj))


def pytest_pyfunc_call(pyfuncitem):
    """
    Run asyncio test functions in an event loop instead of a normal
    function call.
    """
    funcargs = pyfuncitem.funcargs
    if 'loop' in funcargs:
        loop = funcargs['loop']
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        loop.run_until_complete(pyfuncitem.obj(**testargs))
        return True


@pytest.fixture
def port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.yield_fixture
def loop(request):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)
    loop.set_debug(False)

    yield loop

    loop.stop()
    loop.run_forever()
    loop.close()
    asyncio.set_event_loop(None)


@pytest.yield_fixture
def server(tmpworkdir, loop, port):
    app = handler = srv = None

    async def create(prefix='/'):
        nonlocal app, handler, srv
        app = create_app(tmpworkdir, prefix, loop)

        handler = app.make_handler(keep_alive_on=False)
        domain = '127.0.0.1'
        srv = await loop.create_server(handler, domain, port)
        url = 'http://{}:{}'.format(domain, port)
        return app, url

    yield create

    async def finish():
        await handler.finish_connections()
        await app.finish()
        if srv:
            srv.close()
            await srv.wait_closed()

    loop.run_until_complete(finish())


class Client:
    def __init__(self, loop, url):
        self._session = aiohttp.ClientSession(loop=loop)
        if not url.endswith('/'):
            url += '/'
        self.url = url

    def close(self):
        self._session.close()

    def get(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self.url + path
        return self._session.get(url, **kwargs)

    def post(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self.url + path
        return self._session.post(url, **kwargs)

    def ws_connect(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self.url + path
        return self._session.ws_connect(url, **kwargs)


@pytest.yield_fixture
def client(loop, server):
    app, url = loop.run_until_complete(server())
    client = Client(loop, url=url)
    yield client

    client.close()
