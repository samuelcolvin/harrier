import time
from datetime import datetime
from fnmatch import fnmatch
from multiprocessing import Process
import subprocess
import shlex

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileMovedEvent

from .config import Config
from .common import logger, HarrierProblem
from .build import Builder
from .serve import serve

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
        super().__init__(*args, **kwargs)
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
            raise HarrierProblem('build failed')

    def wait(self):
        while True:
            time.sleep(1)
            self.check_build()


class Subprocess:
    def __init__(self, command):
        logger.info('starting subprocess "%s"', command)
        args = shlex.split(command)
        self.p = subprocess.Popen(args)

    def terminate(self):
        if self.p.returncode is not None:
            self.p.terminate()


def watch(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler(config)
    logger.info('Watch mode starting...')
    event_handler.build()
    event_handler.check_build()

    server_process = Process(target=serve, args=(config.target_dir, config.serve_port))
    server_process.start()

    subprocesses = [Subprocess(c) for c in config.subprocesses]

    observer.schedule(event_handler, config.root, recursive=True)
    observer.start()
    try:
        event_handler.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.warning('killing dev server')
        [p.terminate() for p in subprocesses]
        observer.stop()
        observer.join()
        server_process.terminate()
        time.sleep(0.5)
