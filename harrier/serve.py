import time
from datetime import datetime
from fnmatch import fnmatch
from multiprocessing import Process

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileMovedEvent
from livereload import Server

from .config import Config
from .common import logger, HarrierKnownProblem
from .build import Builder

# specific to jetbrains I think, very annoying if not ignored
JB_BACKUP_FILE = '*___jb_???___'


class HarrierEventHandler(PatternMatchingEventHandler):
    patterns = ['*.*']
    ignore_directories = True

    ignore_patterns = [
        '*/.git/*',
        '*/.idea/*',
        JB_BACKUP_FILE,
    ]

    def __init__(self, config, *args, **kwargs):
        super(HarrierEventHandler, self).__init__(*args, **kwargs)
        self._config = config
        self.build_no = 0
        self._builder = Builder(config)
        self._passing = True
        self._build_time = datetime.now()

    def on_any_event(self, event):
        if isinstance(event, FileMovedEvent):
            if fnmatch(event._src_path, JB_BACKUP_FILE) or fnmatch(event._dest_path, JB_BACKUP_FILE):
                return
        since_build = (datetime.now() - self._build_time).total_seconds()
        if since_build <= 1:
            logger.debug('%s | %0.3f seconds since last build, skipping build', event, since_build)
            return
        logger.debug('%s | %0.3f seconds since last build, building', event, since_build)
        self.build()

    def build(self):
        self._passing = None
        start = datetime.now()
        try:
            self.build_no += 1
            time.sleep(0.05)
            logger.info('change detected, rebuilding ({})...'.format(self.build_no))
            self._builder.build(partial=True)
        except Exception:
            self._passing = False
            raise
        else:
            self._passing = True
        finally:
            self._build_time = datetime.now()
            logger.info('build %d finished in %0.2fs', self.build_no, (self._build_time - start).total_seconds())

    def check_build(self):
        while not isinstance(self._passing, bool):
            time.sleep(0.1)
        if not self._passing:
            raise HarrierKnownProblem('build failed')

    def wait(self):
        while True:
            time.sleep(1)
            self.check_build()


def serve(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler(config)
    logger.info('Watch mode starting...')
    event_handler.build()
    event_handler.check_build()

    server_process = Process(target=_server, args=(config.target_dir, config.serve_port))
    server_process.start()

    observer.schedule(event_handler, config.root, recursive=True)
    observer.start()
    try:
        event_handler.wait()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        server_process.terminate()


def _server(watch_root, port):
    server = Server()
    watch_root = watch_root.rstrip('/') + '/'
    server.watch(watch_root)

    server.serve(root=watch_root, port=port)
