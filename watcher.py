"""
watcher monitors the current notes directory for changes, providing a way to
automatically update the database and git repository whenever a note file is created or modified.
"""

import time

from watchdog.events import LoggingEventHandler, FileSystemEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore

from noted.settings import load_configuration
from noted.utils import create_logger

logger = create_logger(__name__)
project_settings = load_configuration()


class NotedEventHandler(FileSystemEventHandler):
    """ Custom event handler for the noted system.  Only tracks created and modified events"""

    def __init__(self, file_suffix='.md',
                 create_processor=lambda e: logger.info("file created: %s", e.src_path),
                 modified_processor=lambda e: logger.info("file modified: %s", e.src_path)):
        super(NotedEventHandler, self).__init__()
        self.file_suffix = file_suffix
        self.create_processor = create_processor
        self.modified_processor = modified_processor

    def on_created(self, event):
        """ Track file creation """
        current_path: str = event.src_path  # type: ignore
        if current_path.endswith(self.file_suffix):
            # logger.info("A file was created: %s", event.src_path)
            self.create_processor(event)

    def on_modified(self, event):
        """ Track file modification """
        current_path: str = event.src_path  # type: ignore
        if current_path.endswith(self.file_suffix):
            # logger.info("A file was modified: %s", event.src_path)
            self.modified_processor(event)


if __name__ == "__main__":
    # monitor the notes path
    path = project_settings.notes_path

    # Initialize  event handler
    event_handler = NotedEventHandler()

    # Initialize Observer
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)

    # Start the observer
    observer.start()
    try:
        while True:
            # Set the thread sleep time
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
