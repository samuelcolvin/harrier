from tests.conftest import mktree
from .conftest import Client


async def test_simple_file(tmpworkdir, client):
    mktree(tmpworkdir, {
        'foo': 'X',
    })
    r = await client.get('/foo')
    assert r.status == 200
    content = await r.read()
    assert content == b'X'


async def test_prefix_file(tmpworkdir, loop, server):
    app, url = await server('/this_is_prefix/')
    client = Client(loop, url=url)

    mktree(tmpworkdir, {
        'foo': 'X',
    })
    r = await client.get('/this_is_prefix/foo')
    assert r.status == 200
    content = await r.read()
    assert content == b'X'

    client.close()
