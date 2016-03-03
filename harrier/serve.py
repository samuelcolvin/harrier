import json
import logging
import re
from pathlib import Path

import click
import aiohttp
from aiohttp.web_exceptions import HTTPNotModified
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
        super(DevLogHandler, self).__init__(*args)
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


def serve(serve_root, port):
    app = web.Application()
    app[WS] = []
    serve_root = serve_root.rstrip('/') + '/'

    app.router.add_route('GET', '/livereload.js', lr_script_handler)
    app.router.add_route('GET', '/livereload', websocket_handler)

    app.router.register_route(HarrierStaticRoute('static-router', '/', serve_root))

    # TODO in theory file watching could be replaced by accessing tool_chain.source_map
    observer = Observer()
    event_handler = DevServerEventEventHandler(app, serve_root)
    observer.schedule(event_handler, serve_root, recursive=True)
    observer.start()

    logger.info('Started dev server at http://localhost:%s, use Ctrl+C to quit', port)

    try:
        web.run_app(app, port=port, print=lambda msg: None)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


class DevServerEventEventHandler(FileSystemEventHandler):
    def __init__(self, app, serve_root):
        super(DevServerEventEventHandler, self).__init__()
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
            data = json.loads(msg.data)
            command = data['command']
            if command == 'hello':
                if 'http://livereload.com/protocols/official-7' not in data['protocols']:
                    logger.error('live reload protocol 7 not supported by client %s', data)
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
                logger.error('Unknown ws message %s', data)
        elif msg.tp == aiohttp.MsgType.error:
            logger.error('ws connection closed with exception %s' % ws.exception())
        else:
            logger.error('unknown websocket message type %s, data: %s', ws_type_lookup[msg.tp], msg.data)

    # TODO gracefully close websocket connections on app shutdown
    logger.debug('browser disconnected')
    request.app[WS].remove(ws)

    return ws


class HarrierStaticRoute(StaticRoute):
    async def handle(self, request):
        filename = request.match_info['filename']
        try:
            filepath = self._directory.joinpath(filename).resolve()
        except (ValueError, FileNotFoundError):
            pass
        else:
            if filepath.is_dir():
                request.match_info['filename'] = str(filepath.joinpath('index.html').relative_to(self._directory))
        status, length = 'unknown', 0
        try:
            response = await super(HarrierStaticRoute, self).handle(request)
        except HTTPNotModified:
            status, length = 304, 0
            raise
        else:
            status, length = response.status, response.content_length
        finally:
            logger.info(' > %s %s %s %s', request.method, request.path, status, self.fmt_size(length))
        return response

    @staticmethod
    def fmt_size(num):
        if num < 1024:
            return '{:0.0f}B'.format(num)
        else:
            return "{:0.0f}KB".format(num / 1024)
