import logging
import json
from pathlib import Path

import pytest
import aiohttp
from watchdog.events import FileSystemEvent

from harrier.serve import WS, DevServerEventEventHandler, _get_asset_content, _fmt_size

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


async def test_404(tmpworkdir, loop, server):
    app, url = await server('/this_is_prefix/')
    client = Client(loop, url=url)

    mktree(tmpworkdir, {
        'foo': 'X',
    })
    r = await client.get('/this_is_prefix/foo')
    assert r.status == 200
    content = await r.read()
    assert content == b'X'

    r = await client.get('/this_is_prefix/foobar')
    assert r.status == 404
    content = await r.read()
    assert content == b'404: Not Found\n\n'

    r = await client.get('/foobar')
    assert r.status == 404
    content = await r.read()
    assert content == b'404: Not Found (files are being served from the subdirectory "/this_is_prefix/" only)\n\n'

    client.close()


async def test_304(tmpworkdir, client, logcap):
    logcap.set_logger('dev_server', logging.INFO)
    mktree(tmpworkdir, {
        'foo': 'X',
    })
    r = await client.get('/foo', headers={'IF-MODIFIED-SINCE': 'Mon, 03 Jan 2050 00:00:00 UTC'})
    assert r.status == 304
    content = await r.read()
    assert content == b''
    assert logcap.log == ' > GET /foo 304 0B\n'


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


class MockWS:
    def __init__(self):
        self.sent_strs = []

    def send_str(self, s):
        self.sent_strs.append(s)


def test_event_handler_one_client(logcap):
    logcap.set_logger('dev_server', logging.INFO)
    app = {WS: [MockWS()]}
    hdl = DevServerEventEventHandler(app, 'foobar')
    event = FileSystemEvent('foobar/whatever.js')
    hdl.on_any_event(event)
    ws = app[WS][0]
    assert len(ws.sent_strs) == 1
    data = json.loads(ws.sent_strs[0])
    assert data == {'liveCSS': True, 'path': 'whatever.js', 'command': 'reload', 'liveImg': True}
    assert logcap.log == 'prompting reload of whatever.js on 1 client\n'


def test_event_handler_two_clients(logcap):
    logcap.set_logger('dev_server', logging.INFO)
    app = {WS: [MockWS(), MockWS()]}
    hdl = DevServerEventEventHandler(app, 'foobar')
    event = FileSystemEvent('foobar/whatever.js')
    hdl.on_any_event(event)
    assert logcap.log == 'prompting reload of whatever.js on 2 clients\n'


@pytest.mark.parametrize('v,result', [
    (None, ''),
    (Path('assets.json'), 'Asset file contents:\n\n{"x.js": "wherever/x.js"}'),
], ids=['None', 'assets.json'])
def test_get_asset_content(v, result, tmpworkdir):
    mktree(tmpworkdir, {
        'assets.json': '{"x.js": "wherever/x.js"}',
    })
    assert _get_asset_content(v) == result


@pytest.mark.parametrize('v,result', [
    ('', ''),
    (123, '123B'),
    (1230, '1.2KB'),
])
def test_fmt_size(v, result):
    assert _fmt_size(v) == result
