"""
db.py

Simplified database scheme for noted database.

Tables include:
    notes
    keywords -- one-to-many relationship with notes
    present -- one-to-many relationship with notes
    speakers -- one-to-many relationship with notes

"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData,
    DateTime,
    create_engine,
    select,
    insert,
    ForeignKeyConstraint, text
)
from sqlalchemy.engine import Engine, Connection

from noted.notes import Note
from noted.settings import load_configuration
from noted.utils import create_logger, debugging

# from sqlite3 import Row

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
    Column("keywords", String),
    Column("present", String),
    Column("speakers", String),
)

# noinspection PyUnresolvedReferences
keywords = Table(
    "keywords",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, index=True),
    Column("note_id", Integer, nullable=False),
    ForeignKeyConstraint(("note_id",), ["notes.id"]),
)

present = Table(
    "present",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("note_id", Integer, nullable=False),
)

speakers = Table(
    "speakers",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("note_id", Integer, nullable=False),
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


def already_stored(eng: Engine, filename: str, timestamp: datetime) -> bool:
    """
    Determine whether the note is already in the database based on its name and timestamp.

    Args:
        eng: the connection to the database
        filename: the filename of the note to be checked
        timestamp: the timestamp of the note to be checked

    Returns: True if the note is already in the database.
    """
    with eng.begin() as conn:
        stmt = notes.select().where(
            notes.c.filename == filename, notes.c.timestamp == timestamp  # type: ignore
        )
        return conn.execute(stmt).fetchone() is not None


def insert_metadata(conn: Connection, table_name: str, data: str, note_id: int) -> int:
    """
    Insert metadata for a note and update link.
    Args:
        conn: The current database connection/transaction
        table_name: The name of the metadata table (keywords, present, speakers)
        data: the keyword|speaker|present value to associate with note_id
        note_id: The id of the note associated with this metadata

    Returns: The id of the inserted metadata.
    """
    if table_name.startswith("keyword"):
        table = keywords
    elif table_name.startswith("present"):
        table = present
    elif table_name.startswith("speakers"):
        table = speakers
    else:
        raise ValueError(f"invalid table name: {table_name}")
    # check to see if already exists
    stmt = select(table).where(table.c.name == data).where(table.c.note_id == note_id)
    row = conn.execute(stmt).fetchone()
    if row:
        logger.debug("found previous insertion: %s", f"{row}")
        meta_id = row[0]
    else:
        # create new entry
        logger.debug("inserting into table %s data %s note_id %d", f"{table}", data, note_id)
        stmt = insert(table).values(name=data, note_id=note_id)
        logger.debug("inserted %s into table %s with note_id %d", data, table_name, note_id)
        meta_id: int = conn.execute(stmt).inserted_primary_key[0]
    return meta_id


class OverwriteAttemptError(Exception):
    """Raised when there is an attempt to overwrite an existing database entry"""


def add_note(eng: Engine, note: Note) -> int:
    """
    Adds the note to the database.  Automatically inserts keywords, present, speakers.

    Args:
        eng: the connection to the database
        note: the note to be added

    Exceptions:
        OverwriteAttemptError when trying to overwrite an existing file

    Returns: the id of the inserted note
    """
    with eng.begin() as conn:
        # first check if there is an existing entry with the same filename and timestamp
        # stmt = notes.select().where(
        #     notes.c.filename == note.filename, notes.c.timestamp == note.timestamp  # type: ignore
        # )
        # row = conn.execute(stmt).fetchone()
        # if row:
        if already_stored(eng, note.filename, note.timestamp):
            raise OverwriteAttemptError(
                f"attempt to overwrite note: {note.filename}:{note.timestamp}"
            )
        logger.debug("adding %s to database", note.filename)
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


def make_search_statement(meta_table: str, exact: bool) -> str:
    """Creates a search statement based on the provided meta_table.

    meta_table can be one of keywords, present, or speakers

    if exact is false, uses LIKE as the test operator.
    """
    notes_table = "notes"
    meta_table = "keywords"
    if exact:
        test_operator = "="
    else:
        test_operator = "LIKE"

    stmt = f"""SELECT * FROM {notes_table} WHERE {notes_table}.id IN (SELECT {meta_table}.note_id FROM {meta_table} 
                 JOIN {notes_table} ON {meta_table}.name {test_operator} :data)"""
    logger.debug(stmt)
    return stmt


def search_by_keyword(eng: Engine, keyword: str, exact: bool = False) -> list[Note]:
    """
    find the database entries corresponding to the keyword and
    return them as a list of Note.

    The default is for keyword to be treated as a "stem", in that the search will use
    the SQL selector LIKE keyword% to find the matches.  A search
    for the keyword "bob" will match "bobby" and "bobo" as well.

    If exact is true, then "bob" only matches "bob".
    """
    if not exact:
        keyword.replace("*", "")  # clean any wildcards
        keyword = f"{keyword}%"
    conn = eng.connect()
    stmt = make_search_statement("keywords", exact)
    logger.debug(stmt)
    rows = conn.execute(text(stmt), {"data": keyword}).fetchall()
    result: list[Note] = []
    for row in rows:
        logger.debug(f"{row}")
        n = Note(page_header=row[1],
                 filename=row[1],
                 keywords=row[4],
                 present=row[5],
                 speakers=row[6],
                 timestamp=row[2],
                 )
        n.body = row[3]
        logger.info(f"{n}")
        result.append(n)
    return result


if __name__ == '__main__':
    print("creating database for testing purposes only")

    MOCK_DIR_NAME = ""
    MOCK_DB_NAME = "test_noted.db"
    database_dir_path = Path(MOCK_DIR_NAME)
    FAKE_NOTES = [
        Note("note one", f"{MOCK_DIR_NAME}/note_one.md", keywords=["one", "two", "three"]),
        Note("note two", f"{MOCK_DIR_NAME}/note_two.md", keywords=["four", "two", "three"]),
        Note("note three", f"{MOCK_DIR_NAME}/note_three.md", keywords=["four", "five", "three"]),
    ]
    db_path = database_dir_path / Path(MOCK_DB_NAME)
    engine = connect_to_database(db_path)
    for note in FAKE_NOTES:
        add_note(engine, note)
