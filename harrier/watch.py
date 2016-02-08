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

    def on_any_event(self, event):
        print(event)
        time.sleep(2.5)
        print(event, 'done')


def watch(config: Config):
    observer = Observer()
    event_handler = HarrierEventHandler()
    observer.schedule(event_handler, config.root, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
