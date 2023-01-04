"""
tests for db.py
"""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from noted.db import connect_to_database, add_note, notes, keywords, search_by_keyword, search_by_file, count_notes, \
    find_all_notes
from noted.notes import Note
from noted.utils import create_logger

logger = create_logger(__name__)
MOCK_DIR_NAME = "mock"
MOCK_DB_NAME = "mock.db"

FAKE_NOTES = [
    Note("note one", f"{MOCK_DIR_NAME}/note_one.md", keywords=["one", "two", "three"]),
    Note("note two", f"{MOCK_DIR_NAME}/note_two.md", keywords=["four", "two", "three"]),
    Note("note three", f"{MOCK_DIR_NAME}/note_three.md", keywords=["four", "five", "three"]),
]


@pytest.fixture()
def database_dir_path() -> Path:
    """
    create a temporary path to store mock databases
    """
    dir_path = Path(MOCK_DIR_NAME)
    db_path = dir_path / Path(MOCK_DB_NAME)
    logger.debug("creating database directory: %s", dir_path.absolute())
    # ensure previous version of database is erased if it exists
    if db_path.exists():
        db_path.unlink()
    # if the directory is not yet available, create it
    if not dir_path.exists():
        dir_path.mkdir()
    # return dir_path
    yield dir_path
    if db_path.exists():
        db_path.unlink()
    if dir_path.exists():
        dir_path.rmdir()


@pytest.fixture()
def database_engine(database_dir_path) -> Engine:
    """
    create a temporary database engine connected to the
    temporary database
    """
    db_path = database_dir_path / Path(MOCK_DB_NAME)
    engine = connect_to_database(db_path)
    return engine


def test_database_dir_path(database_dir_path):
    assert database_dir_path.exists()
    db_path = database_dir_path / Path(MOCK_DB_NAME)
    assert not db_path.exists()


def test_connect_to_database(database_dir_path):
    db_path = database_dir_path / Path(MOCK_DB_NAME)
    assert not db_path.exists()
    engine = connect_to_database(db_path)
    assert engine is not None
    assert db_path.exists()


def test_add_notes(database_engine):
    add_note(database_engine, FAKE_NOTES[0])
    add_note(database_engine, FAKE_NOTES[1])
    add_note(database_engine, FAKE_NOTES[2])
    stmt = select(notes)
    conn = database_engine.connect()
    rows = conn.execute(stmt).all()
    assert len(rows) == 3
    stmt = select(notes).where(notes.c.filename == FAKE_NOTES[0].filename)
    row = conn.execute(stmt).fetchone()
    assert row is not None


def test_keywords_added(database_engine):
    the_id = add_note(database_engine, FAKE_NOTES[0])
    stmt = select(keywords).where(keywords.c.note_id == the_id)
    conn = database_engine.connect()
    rows = conn.execute(stmt).fetchall()
    assert len(rows) == 3


def test_search_by_keyword(database_engine):
    add_note(database_engine, FAKE_NOTES[0])
    add_note(database_engine, FAKE_NOTES[1])
    add_note(database_engine, FAKE_NOTES[2])
    found: list[Note] = search_by_keyword(database_engine, "two", exact_match=True)
    assert len(found) == 2
    assert found[0].filename.endswith("note_one.md")
    assert found[1].filename.endswith("note_two.md")
    found: list[Note] = search_by_keyword(database_engine, "tw")
    assert len(found) == 2
    found: list[Note] = search_by_keyword(database_engine, "th")
    assert len(found) == 3
    found: list[Note] = search_by_keyword(database_engine, "o")
    assert len(found) == 1


def test_search_by_file(database_engine):
    add_note(database_engine, FAKE_NOTES[0])
    add_note(database_engine, FAKE_NOTES[1])
    add_note(database_engine, FAKE_NOTES[2])
    found: list[Note] = search_by_file(database_engine, "two")
    assert len(found) == 1
    assert found[0].filename.endswith("note_two.md")
    found: list[Note] = search_by_file(database_engine, "tw")
    assert len(found) == 1
    assert found[0].filename.endswith("note_two.md")
    found: list[Note] = search_by_file(database_engine, "four")
    assert len(found) == 0


def test_find_all_notes(database_engine):
    add_note(database_engine, FAKE_NOTES[0])
    add_note(database_engine, FAKE_NOTES[1])
    add_note(database_engine, FAKE_NOTES[2])
    found: list[Note] = find_all_notes(database_engine)
    assert len(found) == 3


def test_find_all_notes_empty_database(database_engine):
    found: list[Note] = find_all_notes(database_engine)
    assert len(found) == 0


def test_count_notes(database_engine):
    add_note(database_engine, FAKE_NOTES[0])
    add_note(database_engine, FAKE_NOTES[1])
    add_note(database_engine, FAKE_NOTES[2])
    assert count_notes(database_engine) == 3


def test_count_empty_database(database_engine):
    assert count_notes(database_engine) == 0
