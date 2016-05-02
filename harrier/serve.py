import logging
import asyncio
import re
import json
from pathlib import Path

import click
import aiohttp
from aiohttp.web_exceptions import HTTPNotModified, HTTPNotFound
from aiohttp import web
from aiohttp.web_urldispatcher import StaticRoute
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger('dev_server')

WS = 'websockets'


class DevLogHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'white',
        logging.INFO: 'blue',
        logging.WARN: 'yellow',
    }

    def __init__(self, *args):
        super().__init__(*args)
        self._width = click.get_terminal_size()[0]

    def emit(self, record):
        log_entry = self.format(record)
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno == logging.INFO and msg.startswith(' >'):
            msg = '{} {}'.format(click.style(' >', fg='blue'), msg[3:])
        else:
            msg = click.style(msg, fg=self.colours.get(record.levelno, 'red'))
        click.echo(time + msg)

handler = DevLogHandler()
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def serve(serve_root, subdirectory, port, asset_file=None):
    app = create_app(serve_root, subdirectory=subdirectory, asset_file=asset_file)

    # TODO in theory file watching could be replaced by accessing tool_chain.source_map
    observer = Observer()
    event_handler = DevServerEventEventHandler(app, serve_root)
    observer.schedule(event_handler, str(serve_root), recursive=True)
    observer.start()

    logger.info('Started dev server at http://localhost:%s, use Ctrl+C to quit', port)

    try:
        web.run_app(app, port=port, print=lambda msg: None)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


def create_app(serve_root, subdirectory, asset_file, loop=None):
    loop = loop or asyncio.new_event_loop()
    app = web.Application(loop=loop)
    app[WS] = []

    app.router.add_route('GET', '/livereload.js', lr_script_handler)
    app.router.add_route('GET', '/livereload', websocket_handler)

    assert_path = asset_file and serve_root / asset_file
    serve_root = str(serve_root) + '/'
    app.router.register_route(HarrierStaticRoute('static-router', subdirectory, serve_root, assert_path=assert_path))
    if subdirectory != '/':
        app.router.add_route('*', '/{path:.*}', OutsideSubdirectory(subdirectory, assert_path))
    return app


class DevServerEventEventHandler(FileSystemEventHandler):
    def __init__(self, app, serve_root):
        super().__init__()
        self._serve_root = serve_root
        self._app = app

    def on_any_event(self, event):
        path = Path(event.src_path).relative_to(self._serve_root)
        clients = len(self._app[WS])
        logger.info('prompting reload of %s on %d client%s', path, clients, '' if clients == 1 else 's')
        for i, ws in enumerate(self._app[WS]):
            data = {
                'command': 'reload',
                'path': str(path),
                'liveCSS': True,
                'liveImg': True,
            }
            ws.send_str(json.dumps(data))


async def lr_script_handler(request):
    script_key = 'livereload_script'
    lr_script = request.app.get(script_key)
    if lr_script is None:
        lr_path = Path(__file__).absolute().parent.joinpath('livereload.js')
        with lr_path.open('rb') as f:
            lr_script = f.read()
            request.app[script_key] = lr_script
    return web.Response(body=lr_script, content_type='application/javascript')


async def websocket_handler(request):

    ws = web.WebSocketResponse()
    request.app[WS].append(ws)
    await ws.prepare(request)
    ws_type_lookup = {k.value: v for v, k in aiohttp.MsgType.__members__.items()}

    async for msg in ws:
        if msg.tp == aiohttp.MsgType.text:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError as e:
                logger.error('JSON decode error: %s', str(e))
            else:
                command = data['command']
                if command == 'hello':
                    if 'http://livereload.com/protocols/official-7' not in data['protocols']:
                        logger.error('live reload protocol 7 not supported by client %s', msg.data)
                        ws.close()
                    else:
                        handshake = {
                            'command': 'hello',
                            'protocols': [
                                'http://livereload.com/protocols/official-7',
                            ],
                            'serverName': 'livereload-aiohttp',
                        }
                        ws.send_str(json.dumps(handshake))
                elif command == 'info':
                    logger.info('browser connected at %s', data['url'])
                    logger.debug('browser plugins: %s', data['plugins'])
                else:
                    logger.error('Unknown ws message %s', msg.data)
        elif msg.tp == aiohttp.MsgType.error:
            logger.error('ws connection closed with exception %s',  ws.exception())
        else:
            logger.error('unknown websocket message type %s, data: %s', ws_type_lookup[msg.tp], msg.data)

    # TODO gracefully close websocket connections on app shutdown
    logger.debug('browser disconnected')
    request.app[WS].remove(ws)

    return ws


class HarrierStaticRoute(StaticRoute):
    def __init__(self, *args, **kwargs):
        self._asset_path = kwargs.pop('assert_path', None)
        super().__init__(*args, **kwargs)

    async def handle(self, request):
        filename = request.match_info['filename']
        try:
            filepath = self._directory.joinpath(filename).resolve()
        except (ValueError, FileNotFoundError, OSError):
            pass
        else:
            if filepath.is_dir():
                request.match_info['filename'] = str(filepath.joinpath('index.html').relative_to(self._directory))
        status, length = 'unknown', ''
        try:
            response = await super().handle(request)
        except HTTPNotModified:
            status, length = 304, 0
            raise
        except HTTPNotFound:
            _404_msg = '404: Not Found\n\n' + _get_asset_content(self._asset_path)
            response = web.Response(body=_404_msg.encode('utf8'), status=404)
            status, length = response.status, response.content_length
        else:
            status, length = response.status, response.content_length
        finally:
            l = logger.info if status in {200, 304} else logger.warning
            l(' > %s %s %s %s', request.method, request.path, status, _fmt_size(length))
        return response


class OutsideSubdirectory:
    def __init__(self, prefix, assert_path):
        self._asset_path = assert_path
        self._msg = '404: Not Found (files are being served from the subdirectory "{}" only)\n\n'.format(prefix)

    async def __call__(self, request):
        msg = self._msg + _get_asset_content(self._asset_path)
        r = web.Response(body=msg.encode('utf8'), status=404)
        logger.warning(' > %s %s %s %s', request.method, request.path, r.status, _fmt_size(r.content_length))
        return r


def _get_asset_content(asset_path):
    if not asset_path:
        return ''
    with asset_path.open() as f:
        return 'Asset file contents:\n\n{}'.format(f.read())


def _fmt_size(num):
    if num == '':
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return "{:0.1f}KB".format(num / 1024)
