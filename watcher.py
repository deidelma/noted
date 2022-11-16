"""
watcher monitors the current notes directory for changes, providing a way to
automatically update the database and git repository whenever a note file is created or modified.
"""

import datetime
from pathlib import Path
import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore

from noted.settings import load_configuration
from noted.utils import create_logger

logger = create_logger(__name__)
project_settings = load_configuration()


class NotedEventHandler(FileSystemEventHandler):
    """Custom event handler for the noted system.  Only tracks created and modified events"""

    def __init__(
        self,
        file_suffix=".md",
        create_processor=lambda e: logger.info("file created: %s", e.src_path),
        modified_processor=lambda e: logger.info("file modified: %s", e.src_path),
    ):
        super(NotedEventHandler, self).__init__()
        self.file_suffix = file_suffix
        self.create_processor = create_processor
        self.modified_processor = modified_processor

    def on_created(self, event: FileSystemEvent):
        """Track file creation"""
        current_path: str = event.src_path  # type: ignore
        if current_path.endswith(self.file_suffix):
            # logger.info("A file was created: %s", event.src_path)
            self.create_processor(event)

    def on_modified(self, event: FileSystemEvent):
        """Track file modification"""
        current_path: str = event.src_path  # type: ignore
        if current_path.endswith(self.file_suffix):
            # logger.info("A file was modified: %s", event.src_path)
            self.modified_processor(event)


MODIFIED_FILES : dict[str, datetime.datetime] = {}

def handle_modified_event(evt: FileSystemEvent) -> None:
    """Custom handler for file modification"""
    logger.info("handling %s", evt.src_path)
    MODIFIED_FILES[evt.src_path] = datetime.datetime.now()


if __name__ == "__main__":
    # monitor the notes path
    path = project_settings.notes_path
    logger.info("monitoring directory: %s", path)

    # Initialize  event handler
    event_handler = NotedEventHandler(modified_processor=handle_modified_event)  # type: ignore

    # Initialize Observer
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    logger.info("observer scheduled")

    # Start the observer
    observer.start()
    logger.info("observer started")
    try:
        while True:
            # Set the thread sleep time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("observer interrupted")
        observer.stop()
    observer.join()
    for item in MODIFIED_FILES:
        print(f"File: {Path(item).name} Time: {MODIFIED_FILES[item].isoformat()} Elapsed: {datetime.datetime.now() - MODIFIED_FILES[item]}")
    logger.info("watcher completed")
