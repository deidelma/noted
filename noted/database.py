"""
database.py

Interface to the notes database.

Uses sqlalchemy without an ORM.
"""
from datetime import datetime
from pathlib import Path
from sqlite3 import Row

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData,
    DateTime,
    create_engine,
    text,
    ForeignKeyConstraint,
    func,
    select,
)
from sqlalchemy.engine import Engine, Connection

from dred.notes import Note
from dred.settings import load_configuration
from dred.utils import create_logger, debugging

project_settings = load_configuration()

logger = create_logger(__file__)

metadata_obj = MetaData()

notes = Table(
    "notes",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("filename", String, nullable=False, index=True),
    Column("timestamp", DateTime, nullable=False, index=True),
    Column("body", String, nullable=False),
)

keywords = Table(
    "keywords",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, index=True),
)

present = Table(
    "present",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
)

speakers = Table(
    "speakers",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
)

notes_keywords = Table(
    "notes_keywords",
    metadata_obj,
    Column("note_id", Integer, nullable=False, primary_key=True),
    Column("meta_id", Integer, nullable=False, primary_key=True),
    ForeignKeyConstraint(["note_id"], ["notes.id"]),
    ForeignKeyConstraint(["meta_id"], ["keywords.id"]),
)

notes_present = Table(
    "notes_present",
    metadata_obj,
    Column("note_id", Integer, nullable=False, primary_key=True),
    Column("meta_id", Integer, nullable=False, primary_key=True),
    ForeignKeyConstraint(["note_id"], ["notes.id"]),
    ForeignKeyConstraint(["meta_id"], ["present.id"]),
)

notes_speakers = Table(
    "notes_speakers",
    metadata_obj,
    Column("note_id", Integer, nullable=False, primary_key=True),
    Column("meta_id", Integer, nullable=False, primary_key=True),
    ForeignKeyConstraint(["note_id"], ["notes.id"]),
    ForeignKeyConstraint(["meta_id"], ["speakers.id"]),
)


def connect_to_database(database_path: Path | str | None = None) -> Engine:
    """
    Connects to the database, creating it if necessary.
    Defaults to the database path from Settings.load_configuration()

    Args:
        database_path: If not None, replaces the path in project_settings.

    Returns: the Engine reference to the current database

    """
    if database_path:
        if isinstance(database_path, str):
            database_path = Path(database_path)
        database_path = database_path.as_posix()
    else:
        database_path = project_settings.database_path
    logger.debug("connecting to database: %s", database_path)
    eng = create_engine(f"sqlite:///{database_path}", echo=debugging(), future=True)
    metadata_obj.create_all(eng)
    return eng


def insert_metadata(conn: Connection, table_name: str, data: str, note_id: int) -> int:
    """
    Insert metadata for a note and update link.
    Args:
        conn: The current database connection/transaction
        table_name: The name of the metadata table (keywords, present, speakers)
        data: The data to store
        note_id: The id of the note associated with this metadata

    Returns: The id of the inserted metadata.
    """
    if table_name.startswith("keyword"):
        table = keywords
        link_table = notes_keywords
    elif table_name.startswith("present"):
        table = present
        link_table = notes_present
    elif table_name.startswith("speakers"):
        table = speakers
        link_table = notes_speakers
    else:
        raise ValueError(f"invalid table name: {table_name}")
    stmt = table.select().where(table.c.name == data)
    row = conn.execute(stmt).fetchone()
    if row:
        meta_id = row[0]
    else:
        stmt = table.insert().values(name=data)  # type: ignore
        meta_id: int = conn.execute(stmt).inserted_primary_key[0]  # type: ignore
    stmt = link_table.insert().values(note_id=note_id, meta_id=meta_id)  # type: ignore
    conn.execute(stmt)
    return meta_id


class OverwriteAttemptError(Exception):
    """Raised when there is an attempt to overwrite an existing database entry"""


def add_note(eng: Engine, note: Note) -> int:
    """
    Adds the note to the database.  Automatically inserts keywords, present, speakers.

    Args:
        eng: the connection to the database
        note: the note to be added

    Returns: the id of the inserted note
    """
    with eng.begin() as conn:
        # first check if there is an existing entry with the same filename and timestamp
        stmt = notes.select().where(
            notes.c.filename == note.filename, notes.c.timestamp == note.timestamp  # type: ignore
        )
        row = conn.execute(stmt).fetchone()
        if row:
            raise OverwriteAttemptError(
                f"attempt to overwrite note: {note.filename}:{note.timestamp}"
            )
        stmt = notes.insert().values(  # type: ignore
            filename=note.filename, timestamp=note.timestamp, body=note.to_markdown()
        )
        result = conn.execute(stmt)
        note_id = result.inserted_primary_key[0]
        for kw in note.keywords:
            insert_metadata(conn, "keywords", kw, note_id)
        for pr in note.present:
            insert_metadata(conn, "present", pr, note_id)
        for speaker in note.speakers:
            insert_metadata(conn, "speakers", speaker, note_id)
    return note_id


def make_search_statement(table: str, wildcard: bool) -> str:
    """
    Given a table name, creates a search statement for use by the find_notes_by_... functions
    Args:
        table: The name of the table (i.e., keywords, present, speakers).
        wildcard: If True, use wildcard to do the search

    Returns: A search statement suitable for use with conn.execute.
    """
    if wildcard:
        equal_operator = "like"
    else:
        equal_operator = "="
    # noinspection SqlResolve
    lines: list[str] = [
        f"select * from notes where notes.id in (select notes_{table}.note_id from notes_{table}",
        f" join {table} on notes_{table}.meta_id = {table}.id ",
        f"where {table}.name {equal_operator} :data)",
    ]
    stmt = " ".join(lines)
    return stmt


def row_to_note(row: Row) -> Note:
    """
    Convert a row returned from the database search to a notes.Note
    Args:
        row: The row, assumed to be a tuple in the order id, filename, timestamp, body.

    Returns: A note corresponding to the row

    """
    _, filename, timestamp, body = row
    n: Note = Note.create_note_from_markdown(body)
    n.timestamp = timestamp
    n.filename = filename
    return n


def sort_by_timestamp(notes_list: list[Note], ascending=True) -> list[Note]:
    """
    Return a sorted list of Note based on the timestamps.

    Args:
        notes_list: Notes to be sorted.
        ascending: If true, sort in ascending order.  Otherwise, descending oder.

    Returns: Sorted list of Note.
    """
    return list(
        sorted(notes_list, key=lambda item: item.timestamp, reverse=not ascending)
    )


def find_notes_by_keyword(
    eng: Engine, keyword: str, wildcard: bool = False
) -> list[Note]:
    """
    Find notes in the database associated with the provided keyword
    Args:
        eng: The current database connection.
        keyword: The keyword to search for.
        wildcard: If True, use a wildcard search with LIKE %keyword%.

    Returns: A list of Note that match the search criterion.

    """
    if wildcard:
        keyword = f"%{keyword}%"
    else:
        keyword = keyword.replace("%", "")
    with eng.begin() as conn:
        # noinspection SqlResolve
        stmt = text(make_search_statement("keywords", wildcard))
        rows = conn.execute(stmt, {"data": keyword}).fetchall()
        logger.debug(
            "found %d notes when searching for keyword: %s", len(rows), keyword
        )
    the_notes = [row_to_note(row) for row in rows]  # type: ignore
    # return [row_to_note(row) for row in rows]  # type: ignore
    the_notes = sort_by_timestamp(the_notes, False)
    return the_notes


def find_notes_by_speaker(
    eng: Engine, speaker: str, wildcard: bool = False
) -> list[Note]:
    """
    Find notes in the database associated with the provided speaker
    Args:
        eng: The current database connection.
        speaker: The speaker to search for.
        wildcard: If True, use a wildcard search with LIKE %keyword%.

    Returns: A list of Note that match the search criterion.

    """
    if wildcard:
        speaker = f"%{speaker}%"
    else:
        speaker = speaker.replace("%", "")
    with eng.begin() as conn:
        # noinspection SqlResolve
        stmt = text(make_search_statement("speakers", wildcard))
        rows = conn.execute(stmt, {"data": speaker}).fetchall()
        logger.debug(
            "found %d notes when searching for speaker: %s", len(rows), speaker
        )
    return sort_by_timestamp([row_to_note(row) for row in rows], False)  # type: ignore


def find_notes_by_present(
    eng: Engine, attendee: str, wildcard: bool = False
) -> list[Note]:
    """
    Find notes in the database associated with the provided attendee
    Args:
        eng: The current database connection.
        attendee: The person to search for.
        wildcard: If True, use a wildcard search with LIKE %keyword%.

    Returns: A list of Note that match the search criterion.

    """
    if wildcard:
        speaker = f"%{attendee}%"
    else:
        speaker = attendee.replace("%", "")
    with eng.begin() as conn:
        # noinspection SqlResolve
        stmt = text(make_search_statement("present", wildcard))
        rows = conn.execute(stmt, {"data": speaker}).fetchall()
        logger.debug(
            "found %d notes when searching for attendee: %s", len(rows), speaker
        )
    the_notes = [row_to_note(row) for row in rows]  # type: ignore
    return sort_by_timestamp(the_notes, False)


def find_notes_by_filename_and_timestamp(
    eng: Engine, filename: str, timestamp: datetime
) -> list[Note]:
    """
    Find notes in the database associated with the provided filename and timestamp.
    Args:
        eng: The current database connection.
        filename: The filename to search for.
        timestamp: The timestamp to search for.

    Returns: A list of Note that match the search criterion.

    """
    with eng.begin() as conn:
        stmt = notes.select().where(
            notes.c.filename == filename, notes.c.timestamp == timestamp
        )
        rows = conn.execute(stmt).fetchall()
        logger.debug(
            "found %d notes_list when searching for filename: %s and timestamp: %s",
            len(rows),
            filename,
            timestamp,
        )
    the_notes = [row_to_note(row) for row in rows]  # type: ignore
    return sort_by_timestamp(the_notes, False)


def find_notes_by_filename(
    eng: Engine, filename: str, wildcard: bool = False
) -> list[Note]:
    """
    Find notes in the database associated with the provided filename.
    Args:
        eng: The current database connection.
        filename: The filename to search for.
        wildcard: If True use LIKE instead of = for the search.

    Returns: A list of Note that match the search criterion.

    """
    with eng.begin() as conn:
        if wildcard:
            stmt = notes.select().where(notes.c.filename.like(f"%{filename}%"))
        else:
            stmt = notes.select().where(notes.c.filename == filename)
        rows = conn.execute(stmt).fetchall()
        logger.debug(
            "found %d notes_list when searching for filename: %s", len(rows), filename
        )
    the_notes = [row_to_note(row) for row in rows]  # type: ignore
    return sort_by_timestamp(the_notes, False)


def find_all_notes(eng: Engine) -> list[Note]:
    """
    Return a list of all notes in the database.

    Args:
        eng (Engine): The current database connection.

    Returns:
        List[Note]: The notes in the database in reverse order by date.
    """
    with eng.begin() as conn:
        stmt = notes.select()
        rows = conn.execute(stmt).fetchall()
        logger.debug("found %d note", len(rows))
    the_notes = [row_to_note(row) for row in rows]  # type: ignore
    return sort_by_timestamp(the_notes, False)


def count_notes(engine: Engine) -> int:
    """Returns the number of notes in the database

    Args:
        engine (Engine): The database connection.

    Returns:
        int: The number of notes.
    """
    with engine.begin() as conn:
        stmt = select(func.count(notes.c.id))
        result = conn.execute(stmt).fetchone()[0]  # type: ignore
    return int(result)
