"""
Module providing scans and searches for the dred project.


"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import sqlalchemy.engine
from sqlalchemy import select

from noted import database
from noted.database import notes
from noted.notes import Note
from noted.settings import load_configuration
from noted.utils import create_logger

project_settings = load_configuration()

logger = create_logger(__name__)


class SearchException(Exception):
    """Raised when there is a search failure."""


def needs_updating(
    timestamp_table: dict[str, datetime],
    file_path: Path,
) -> bool:
    """
    Returns true if the disk version of the file is newer than the one in the database.
    Also returns true if the file is not yet in the database.

    Args:
        timestamp_table (dict): A map between filenames and timestamps.
        file_path (Path): A valid pathlib.Path pointing to the file.
    """
    if file_path.name in timestamp_table:
        ts = datetime.fromtimestamp(file_path.stat().st_mtime)
        return ts > timestamp_table[file_path.name]
    else:
        return True


# noinspection PyArgumentEqualDefault
def process_file(engine: sqlalchemy.engine.Engine, file_path: Path) -> None:
    """
    Processes the file given by the path.

    Args:
        engine (Engine): the currently active database connection.
        file_path (Path): the path to the file
    Exceptions:
        Throws IOError if file cannot be read
    """
    logger.debug("Reading file %s", file_path)
    data = Note.load_file(file_path)
    note = Note.create_note_from_markdown(data.body)
    note.filename = file_path.name
    note.timestamp = data.timestamp
    database.add_note(engine, note)
    logger.debug("Note %s added to database.", note.filename)


def process_files(
    engine: sqlalchemy.engine.Engine,
    notes_path: Path,
    exclude_files: str | list[str] = "",
) -> tuple[int, int]:
    """
    Process all the files in the directory, adding or updating them in the database.

    Args:
        engine: Connection to currently active database.
        notes_path: The Path to the documents
        exclude_files: Exclude any files beginning with the stem in exclude_files

    Returns: result, optional update count . result is 0 on success
    """

    def excluded(a_file: Path, excluded_files: list[str]) -> bool:
        for stem in excluded_files:
            if str(a_file.name).startswith(stem):
                return True
        return False

    if not notes_path.exists():
        logger.critical("%s does not exist", notes_path)
        return 1, 0

    if not notes_path.is_dir():
        logger.critical("%s is not a valid directory.", notes_path.absolute())
        return 1, 0

    # make sure excluded files are in a list
    if isinstance(exclude_files, str):
        exclude_files = list(exclude_files)
    stmt = select(notes.c.filename, notes.c.timestamp)  # type: ignore
    with engine.begin() as conn:
        result = conn.execute(stmt).fetchall()
    if result is None:
        logger.critical("No result in search for filenames and timestamps.")
        raise SearchException("unable to find notes in database")
    timestamp_table = {row[0]: row[1] for row in result}

    files = list(notes_path.glob("*.md"))
    logger.debug("found %d files in %s", len(files), notes_path)
    update_count = 0
    for the_file in files:
        if not excluded(the_file, exclude_files):
            try:
                if needs_updating(timestamp_table, the_file):
                    process_file(engine, the_file)
                    update_count += 1
            except IOError:
                logger.critical("Error reading %s", f"{the_file}")
                return 1, 0
    logger.debug("Updated database with data from %d files.", len(files))
    logger.info("Updated %d files.", update_count)
    # debug("logged")
    return 0, update_count


def do_scan(
    notes_dir: str = "", db_pathname: str = "", exclude: str | list[str] = ""
) -> tuple[int, int]:
    """
    Carry out the scan of the current notes directory, updating the database.

    If notes_dir is empty, defaults to project_settings.notes_dir.
    If db_pathname is empty, defaults to project_settings.db_pathname.
    Will omit files that start with the stems in exclude (e.g., 'crap')

    Returns a tuple.  If successful, the first element is 0, the second is the number of note updated.
    """
    # debug("called")
    if len(notes_dir) == 0:
        notes_dir = project_settings.notes_path
    if len(db_pathname) == 0:
        db_pathname = project_settings.database_path
    logger.debug(
        "scanning directory: %s; updating database: %s", notes_dir, db_pathname
    )
    engine = database.connect_to_database(db_pathname)

    result, count = process_files(
        engine, notes_path=Path(notes_dir), exclude_files=exclude
    )
    return result, count


def do_filename_search(filename: str, db_pathname: str = "") -> list[str]:
    """
    Search for the filenames that match the filepath wildcard passed from the command line.

    Args:
        filename (str) : Filepath to search for.
        db_pathname (str, optional): A pathname to the database allowing injection during testing. Defaults to "".
    Returns:
        list[str]: The list of matching filenames.
    """
    logger.debug("searching for '%s'", filename)
    if db_pathname == "":
        db_pathname = project_settings.database_path
    engine = database.connect_to_database(db_pathname)
    items = database.find_notes_by_filename(engine, filename)
    return [note.filename for note in items]


def do_filename_search_by_keyword(
    keyword: str, db_pathname: str = "", verbose: bool = False
) -> list[str]:
    """
    Search for the filenames that match the keyword wildcard passed from the command line.
    Args:
        keyword (str): The key to search for.
        db_pathname (str, optional): A pathname of the database, allowing injection for testing. Defaults to "".
        verbose (bool, optional): If true, print the filenames to stdout. Defaults to False.

    Returns:
        list[str]: The list of matching filenames.
    """
    logger.debug("searching for keyword: '%s'", keyword)
    if db_pathname == "":
        db_pathname = project_settings.database_path
    engine = database.connect_to_database(db_pathname)
    the_notes = database.find_notes_by_keyword(engine, keyword)
    filenames = [n.filename for n in the_notes]
    logger.debug(
        "Found %d unique filenames corresponding to key: %s", len(filenames), keyword
    )
    if verbose:
        for filename in list(filenames):
            print(filename)
    return filenames


def do_note_search_by_keyword(keyword: str, db_pathname: str = "") -> list[Note]:
    """
    Search for the notes that match the keyword wildcard passed from the command line.
    Args:
        keyword (str): The key to search for.
        db_pathname (str, optional): A pathname of the database, allowing injection for testing. Defaults to "".

    Returns:
        list[Note]: The list of matching notes.
    """
    logger.debug("searching for keyword: '%s'", keyword)
    if db_pathname == "":
        db_pathname = project_settings.database_path
    engine = database.connect_to_database(db_pathname)
    the_notes = database.find_notes_by_keyword(engine, keyword)
    logger.debug("found %d notes matching keyword: %s", len(the_notes), keyword)
    return the_notes


# noinspection SqlNoDataSourceInspection
def do_count(db_pathname: str = "") -> int:
    """Returns the number of notes in the database

    Args:
        db_pathname (str): The database location.

    Returns:
        int: The number of notes.
    """
    if db_pathname == "":
        db_pathname = project_settings.database_path
    engine = database.connect_to_database(db_pathname)
    return database.count_notes(engine)


def do_backup(filenames: Optional[list[str]] = None) -> None:
    """
    Backups up the files in the current notes directory.
    If filenames is provided, only backs up those in the list.
    Filenames should not be fully qualified (i.e., bob.md, not /user/notes/bob.md)

    Args:
        filenames (optional): List of files in the notes directory to backup.
    """
    ts = datetime.now().timestamp()
    current_bu_dir_name: str = f"{ts}"
    print(current_bu_dir_name)
    bu_path = Path(project_settings.backup_path).joinpath()

    if __name__ == "main":
        # testing use only
        do_backup()
