import time
import shlex
import subprocess
from datetime import datetime
from fnmatch import fnmatch
from multiprocessing import Process

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
    wait_delay = 1

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

    def wait(self, extra_checks):
        while True:
            time.sleep(self.wait_delay)
            self.check_build()
            if not extra_checks():
                return


class SubprocessController:
    def __init__(self, command):
        self._cmd = command
        logger.info('starting subprocess "%s"', command)
        args = shlex.split(command)
        self.p = subprocess.Popen(args)

    def terminate(self):
        if self.p.returncode is None:
            self.p.terminate()

    def check(self):
        self.p.poll()
        if self.p.returncode is None:
            return True
        if self.p.returncode == 0:
            logger.warning('subprocess "%s" exited', self._cmd)
        else:
            logger.error('subprocess "%s" exited with errors (%r)', self._cmd, self.p.returncode)


class SubprocessGroupController:
    def __init__(self, subprocess_list):
        self.subprocesses = [SubprocessController(c) for c in subprocess_list]

    def check(self):
        return all(s.check() for s in self.subprocesses)

    def terminate(self):
        [p.terminate() for p in self.subprocesses]


def watch(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler(config)
    logger.info('Watch mode starting...')
    event_handler.build()
    event_handler.check_build()

    server_process = Process(target=serve, args=(config.target_dir, config.uri_subdirectory, config.serve_port,
                                                 config.asset_file))
    server_process.start()

    sp_ctrl = SubprocessGroupController(config.subprocesses)

    observer.schedule(event_handler, str(config.root), recursive=True)
    observer.start()
    try:
        event_handler.wait(sp_ctrl.check)
    except KeyboardInterrupt:
        pass
    finally:
        logger.warning('killing dev server')
        sp_ctrl.terminate()
        observer.stop()
        observer.join()
        if server_process.exitcode not in {None, 0}:
            raise RuntimeError('Server process already terminated with exit code {}'.format(server_process.exitcode))
        else:
            server_process.terminate()
            time.sleep(0.1)
