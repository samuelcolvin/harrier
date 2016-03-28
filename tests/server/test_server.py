import json

import aiohttp

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


async def test_index(tmpworkdir, client):
    mktree(tmpworkdir, {
        'index.html': 'abc',
    })
    r = await client.get('/')
    assert r.status == 200
    content = await r.read()
    assert content == b'abc'


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


async def test_livereload(client):
    r = await client.get('/livereload.js')
    assert r.status == 200
    content = await r.read()
    assert b'PROTOCOL_7' in content


async def test_websocket_hello(client):
    async with client.session.ws_connect(client.get_url('livereload')) as ws:
        data = {
            'command': 'hello',
            'protocols': ['http://livereload.com/protocols/official-7']
        }
        ws.send_str(json.dumps(data))
        async for msg in ws:
            assert msg.tp == aiohttp.MsgType.text
            data = json.loads(msg.data)
            assert data == {
                'serverName': 'livereload-aiohttp',
                'command': 'hello',
                'protocols': ['http://livereload.com/protocols/official-7']
            }
            break


async def test_websocket_wrong_protocol(client, capsys):
    async with client.session.ws_connect(client.get_url('livereload')) as ws:
        data = {
            'command': 'hello',
            'protocols': ['http://livereload.com/protocols/official-6']
        }
        ws.send_str(json.dumps(data))
    stdout, _ = capsys.readouterr()
    assert 'live reload protocol 7 not supported by client' in stdout


async def test_websocket_info(client, capsys):
    async with client.session.ws_connect(client.get_url('livereload')) as ws:
        data = {
            'command': 'info',
            'url': 'foobar',
            'plugins': 'bang',
        }
        ws.send_str(json.dumps(data))
    stdout, _ = capsys.readouterr()
    assert 'browser connected at foobar' in stdout


async def test_websocket_command_other(client, capsys):
    async with client.session.ws_connect(client.get_url('livereload')) as ws:
        data = {
            'command': 'other',
        }
        ws.send_str(json.dumps(data))
    stdout, _ = capsys.readouterr()
    assert 'Unknown ws message {"command": "other"}' in stdout


async def test_websocket_bad_json(client, capsys):
    async with client.session.ws_connect(client.get_url('livereload')) as ws:
        ws.send_str('foo')
    stdout, _ = capsys.readouterr()
    assert 'JSON decode error' in stdout
