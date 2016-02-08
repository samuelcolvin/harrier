import time

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from .config import Config
from .build import build


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

    def on_any_event(self, event):
        print(event, build)


def watch(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler(config)
    observer.schedule(event_handler, config.root, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
