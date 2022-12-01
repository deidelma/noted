"""
watcher monitors the current notes directory for changes, providing a way to
automatically update the database and git repository whenever a note file is created or modified.
"""

import datetime
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore

from git import Repo  # type: ignore

from noted.database import already_stored, OverwriteAttemptError
from noted.settings import load_configuration
from noted.utils import create_logger
from noted.searches import do_scan, process_file
from noted import database

logger = create_logger(__name__)
project_settings = load_configuration()


def valid_note(filename: str | Path) -> bool:
    """
    Returns true if the note filename is valid.
    Files ending in .md and not starting with EXCLUDED_FILENAME_STEMS are valid.

    :param filename: A Path or string representation of the filename.
    :return: True if the filename is valid.
    """
    if isinstance(filename, str):
        filepath = Path(filename)
    else:
        filepath = filename
    n = filepath.name.lower()
    if n.startswith("#") or n.startswith(".#"):
        return False
    if n[0:4] in EXCLUDED_FILENAME_STEMS:
        return False
    if n.endswith(".md"):
        return True
    return False


def erase_files(pattern: str):
    """
    Erase files from the notes directory that match the provided pattern.

    Args:
        pattern: A string suitable for use with glob (e.g., '*.*~')
    """
    notes_path = Path(project_settings.notes_path)
    items = list(notes_path.glob(pattern))
    count = len(items)
    if count > 0:
        for item in items:
            item.unlink()
        logger.info("removed %d files of type: %s", count, pattern)


def update_git_repository() -> None:
    """
    Attempts to update the git repository associated with the notes directory.
    Although progress is logged, errors do not result in interruption of the program.
    """
    # first purge detritus
    erase_files("*.*~")
    erase_files("crap*.*")
    erase_files(".#*")
    git_path = Path(project_settings.notes_path).joinpath(".git")
    if not git_path.exists():
        logger.error("Unable to find .git directory.  Has it been initialized?")
        return
    repo = Repo(git_path)
    git = repo.git
    added = git.add("*.md")
    logger.info(added)
    committed = git.commit("-m Update:" + datetime.datetime.now().isoformat())
    logger.info(committed)


class NotedEventHandler(FileSystemEventHandler):
    """Custom event handler for the noted system.  Only tracks created and modified events"""

    def __init__(
        self,
        file_suffix=".md",
        create_processor=lambda evt: logger.info("file created: %s", evt.src_path),
        modified_processor=lambda evt: logger.info("file modified: %s", evt.src_path),
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
        if valid_note(filename):
            self._modified_notes[filename] = datetime.datetime.now()

    def drop_note(self, filename: str) -> None:
        """
        Remove a note from the current table, if it is present

        :param filename: The filename corresponding to the note to remove from the table.
        """
        if filename in self._modified_notes:
            del self._modified_notes[filename]

    def get_timestamp(self, filename: str) -> datetime.datetime:
        """
        Return the timestamp corresponding to the filename.
        N.B. Does not check to ensure that filename is in the table.

        Args:
            filename: the filename of the note

        Returns: datetime timestamp corresponding to this file
        """
        return self._modified_notes[filename]

    def count(self) -> int:
        """
        Count the number of notes currently stored in the table.
        :return: The number of notes.
        """
        return len(self._modified_notes)

    def notes(self) -> list[str]:
        """
        Returns a list of notes currently in the table.

        :return: The notes in the table as a list.
        """
        return list(self._modified_notes.keys())

    def notes_older_than(self, d: datetime.timedelta) -> list[str]:
        """
        Find monitored notes that have been monitored more than delta time before now.

        :param d: The time interval since a note has been updated.
        :return: The filenames of notes updated more than delta seconds ago.
        """
        note_list: list[str] = []
        for filename in self._modified_notes:
            if datetime.datetime.now() - self._modified_notes[filename] > d:
                note_list.append(filename)
        return note_list


MODIFIED_NOTES_TABLE = MonitoredNoteTable()
DATABASE_UPDATE_TIME_DELTA = 60 * 5  # 5 minutes
EXCLUDED_FILENAME_STEMS = {"crap"}  # stems are 4 characters long


def handle_modified_event(evt: FileSystemEvent) -> None:
    """
    Custom handler for file modification

    Args:
        evt: A file creation or modification event.
    """
    logger.debug("handling %s", evt.src_path)
    MODIFIED_NOTES_TABLE.add_note(evt.src_path)


def main():
    # clean up notes that haven't yet been put in the database
    logger.info("scanning files for notes that need to be loaded in the database")
    result, number_updated = do_scan(exclude=list(EXCLUDED_FILENAME_STEMS))
    if result != 0:
        logger.fatal(
            "fatal error: unable to scan directory %s", project_settings.notes_path
        )
        sys.exit(1)
    # monitor the notes path
    logger.info("monitoring directory: %s", project_settings.notes_path)

    # Initialize  event handler
    event_handler = NotedEventHandler(modified_processor=handle_modified_event)  # type: ignore

    # Initialize Observer
    observer = Observer()
    observer.schedule(event_handler, project_settings.notes_path, recursive=True)
    logger.info("observer scheduled")

    # Start the observer
    observer.start()
    logger.info("observer started")
    delta = datetime.timedelta(seconds=DATABASE_UPDATE_TIME_DELTA)
    try:
        while True:
            # Set the thread sleep time
            time.sleep(1)
            logger.debug("The table has %d notes", MODIFIED_NOTES_TABLE.count())
            aged_notes = MODIFIED_NOTES_TABLE.notes_older_than(delta)
            for note in aged_notes:
                logger.debug("%s is more than 10 seconds old", note)
                engine = database.connect_to_database(project_settings.database_path)
                try:
                    p = Path(note)
                    if not valid_note(p):
                        logger.info("invalid note: %s", note)
                    elif already_stored(
                        engine, note, MODIFIED_NOTES_TABLE.get_timestamp(note)
                    ):
                        logger.info(
                            "already stored: %s",
                            note,
                            MODIFIED_NOTES_TABLE.get_timestamp(note).isoformat(),
                        )
                    else:
                        process_file(engine, p)
                        logger.info(
                            "stored %s %s",
                            note,
                            MODIFIED_NOTES_TABLE.get_timestamp(note).isoformat(),
                        )
                        MODIFIED_NOTES_TABLE.drop_note(note)
                except IOError:
                    logger.fatal("Fatal error: Unable to read file %s.", note)
                    sys.exit(1)
                except OverwriteAttemptError:
                    logger.info(
                        "Attempt to overwrite existing record: %s %s",
                        note,
                        MODIFIED_NOTES_TABLE.get_timestamp(note).isoformat(),
                    )
    except KeyboardInterrupt:
        logger.info("observer interrupted")
        observer.stop()
    observer.join()
    update_git_repository()
    logger.info("watcher completed")


if __name__ == "__main__":
    main()
