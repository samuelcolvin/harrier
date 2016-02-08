import time
from multiprocessing import Process

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from livereload import Server

from .config import Config
from .common import logger, HarrierKnownProblem
from .build import build


def build_process(config, build_no):
    time.sleep(0.05)
    logger.info('change detected, rebuilding ({})...'.format(build_no))
    logger.debug(config)
    build(config)
    logger.info('build {} finished'.format(build_no))


class HarrierEventHandler(PatternMatchingEventHandler):
    patterns = ['*.*']
    ignore_directories = True
    ignore_patterns = [
        '*/.git/*',
        '*/.idea/*',
        '*___jb_???___',
    ]

    def __init__(self, config, *args, **kwargs):
        super(HarrierEventHandler, self).__init__(*args, **kwargs)
        self._config = config
        self._build_process = None
        self.build_no = 0

    def on_any_event(self, event):
        self.async_build()

    def async_build(self):
        if self.check_build():
            self.build_no += 1
            self._build_process = Process(target=build_process, args=(self._config, self.build_no))
            self._build_process.start()
        return self._build_process

    def check_build(self):
        if not self._build_process:
            return True
        if self._build_process.exitcode not in {None, 0}:
            raise HarrierKnownProblem('Build Process failed.')
        return self._build_process.exitcode == 0


def serve(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler(config)
    logger.info('Watch mode starting...')
    p = event_handler.async_build()
    p.join()
    event_handler.check_build()

    server_process = Process(target=_server, args=(config.target_dir,))
    server_process.start()

    observer.schedule(event_handler, config.root, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
            event_handler.check_build()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        server_process.terminate()


def _server(watch_root):
    server = Server()
    watch_root = watch_root.rstrip('/') + '/'
    server.watch(watch_root)

    server.serve(root=watch_root)
