"""
watcher monitors the current notes directory for changes, providing a way to
automatically update the database and git repository whenever a note file is created or modified.
"""

import datetime
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


class MonitoredNoteTable:
    """Holds state of currently monitored notes"""

    _modified_notes: dict[str, datetime.datetime]

    def __init__(self):
        self._modified_notes = {}

    def add_note(self, filename: str) -> None:
        """
        Add a note to the current table

        :param filename: The filename corresponding to the note.
        """
        self._modified_notes[filename] = datetime.datetime.now()

    def drop_note(self, filename: str) -> None:
        """
        Remove a note from the current table, if it is present

        :param filename: The filename corresponding to the note to remove from the table.
        """
        if filename in self._modified_notes:
            del self._modified_notes[filename]

    def count(self) -> int:
        """
        Count the number of notes currently stored in the table.
        :return: The number of notes.
        """
        return len(self._modified_notes)

    def notes_older_than(self, d: datetime.timedelta) -> list[str]:
        """
        Find monitored notes that have been monitored more than delta time before now.

        :param d: The time interval since a note has been updated.
        :return: The filenames of notes updated more than delta seconds ago.
        """
        result: list[str] = []
        for filename in self._modified_notes:
            if datetime.datetime.now() - self._modified_notes[filename] > d:
                result.append(filename)
        return result


MODIFIED_NOTES = MonitoredNoteTable()


def handle_modified_event(evt: FileSystemEvent) -> None:
    """Custom handler for file modification"""
    logger.info("handling %s", evt.src_path)
    MODIFIED_NOTES.add_note(evt.src_path)


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
    delta = datetime.timedelta(seconds=10)
    try:
        while True:
            # Set the thread sleep time
            time.sleep(1)
            logger.info("The table has %d notes", MODIFIED_NOTES.count())
            aged_notes = MODIFIED_NOTES.notes_older_than(delta)
            for note in aged_notes:
                logger.info("%s is more than 10 seconds old", note)
                MODIFIED_NOTES.drop_note(note)
    except KeyboardInterrupt:
        logger.info("observer interrupted")
        observer.stop()
    observer.join()
    logger.info("watcher completed")
