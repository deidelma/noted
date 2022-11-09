"""provide backend endpoints"""
import os
import time
import datetime
from pathlib import Path

from flask import Flask, request

from noted.database import connect_to_database, find_all_notes, find_notes_by_filename
from noted.notes import Note
from noted.searches import do_scan
from noted.utils import create_logger
from noted.settings import load_configuration

project_settings = load_configuration()

logger = create_logger(__name__)

app = Flask(__name__)


@app.route('/api/time')
def get_current_time():
    """provide current time as unix timestamp"""
    return {'time': time.asctime()}


@app.route('/api/date')
def get_current_date():
    """Returns a string in the form yyyymmdd"""
    d = datetime.date.today()
    return {'date': d.strftime("%Y%m%d")}


@app.route('/api/create', methods=['POST'])
def create_new_note():
    """Creates a new note"""
    filename = request.form['filename']
    print("create filename: " + filename)
    print("keywords:" + request.form['keywords'])
    return {"result": "OK", "filename": filename}


def create_list_from_word_string(word_string: str) -> list[str]:
    """
    Create a Python list from a comma separated string

    Args:
        word_string (str): the string of words sent by the front end

    Returns:
        str: the list of strings
    """
    return [x.strip() for x in word_string.split(",")]


# @app.route("/api/create/", methods=["post"])
# def create():
#     """Creates a new note with the provided parameters"""
#     the_filename: str = request.params["filename"]  # type:ignore
#     keywords = request.form["keywords"]  # type:ignore
#     present = request.form["present"]  # type:ignore
#     speakers = request.form["speakers"]  # type:ignore
#     if not the_filename:
#         return {"result": "error: no filename provided"}
#     logger.debug("creating note at file: %s", the_filename)
#     complete_filename = Path(project_settings.notes_path).joinpath(the_filename).as_posix()
#     note = Note(
#         filename=the_filename,
#         page_header=the_filename,
#         keywords=create_list_from_word_string(keywords),
#         present=create_list_from_word_string(present),
#         speakers=create_list_from_word_string(speakers),
#     )
#     text = note.to_markdown()
#     # print(text)
#     try:
#         with open(complete_filename, mode="w", encoding="utf-8") as file:
#             file.write(text)
#             logger.debug("wrote %d chars to disk", len(text))
#     except IOError:
#         return {"result": f"error encountered while writing {the_filename}"}
#     return {"result": f"success writing ({len(text)} chars)", "filename": the_filename}


@app.route("/api/findfiles/", methods=["post"])
def find_files():
    """Returns the names of files corresponding to the provided search string"""
    key: str = str(request.form["search_string"]).lower()  # type:ignore
    logger.debug("received request to search for files starting with '%s'", key)
    if not key.endswith("*"):
        key = key + "*.md"
    file_paths = sorted(
        Path(project_settings.notes_path).glob(key), key=os.path.getmtime, reverse=True
    )
    # file_list = [file.name for file in file_paths]
    data = {i: item for i, item in enumerate(file.name for file in file_paths)}
    logger.debug("found %d files with search string: %s", len(data), key)
    # response.content = "application/json"  # type:ignore
    return data


@app.route("/api/findFilesInDatabase/", methods=["post"])
def find_files_in_database():
    """Returns the names of files from the database corresponding to the provided search string"""
    key: str = str(request.form["search_string"]).lower()  # type:ignore
    logger.debug("received request to search for files starting with '%s'", key)
    eng = connect_to_database()
    if key == "":
        note_list = find_all_notes(eng)
    else:
        if key.endswith("*"):
            key = key[0:-1]
        key = f"%{key}%"
        note_list = find_notes_by_filename(eng, key, wildcard=True)
    data = {i: item for i, item in enumerate(note.filename for note in note_list)}
    logger.debug("found %d notes in database", len(data))
    # response.content = "application/json"  # type:ignore
    return data


@app.route("/api/get/", methods=["post"])
def get():
    """Return the note matching the request to the frontend"""
    the_filename = request.form["filename"]  # type:ignore
    logger.debug("get: received request for filename: %s", the_filename)
    note_path = Path(project_settings.notes_path).joinpath(the_filename)
    try:
        with open(note_path, "r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        logger.warning("unable to find file named: %s", the_filename)
        text = "ERROR:NOT FOUND"
    # response.content_type = "application/json"
    data = {"text": text}
    # return dumps(data)
    return data


@app.route("/api/fullPath/", methods=["post"])
def full_path():
    """Return the fully qualified path to the caller
    Assumes that a name with separators is fully qualified.
    """
    name: str = request.form["filename"]  # type:ignore
    if "/" in name or "\\" in name:
        return {"path": name}
    else:
        return {"path": Path(project_settings.notes_path).joinpath(name).as_posix()}


@app.route("/api/store/", methods=["post"])
def store():
    """Called when data is to be stored on disk, after a change."""
    text: str = request.form["text"]  # type:ignore
    the_filename: str = request.params["filename"]  # type:ignore
    if not the_filename:
        logger.debug("no file to write")
        return {"result": "no file to write"}
    try:
        with open(the_filename, mode="w", encoding="utf-8") as file:
            # logger.debug("file: %s storing: %s", filename, text)
            logger.debug("writing %d bytes to file: %s", len(text), the_filename)
            file.write(text)
        return {"result": f"success writing file {the_filename} ({len(text)} chars)"}
    except IOError:
        logger.debug("error encountered while attempting to write file: %s", the_filename)
        return {"result": "error writing file"}


@app.route("/api/list/", methods=['GET'])
def list_notes():
    """Returns a list of notes stored on disk"""

    def modified_time(note_path: Path) -> str:
        """Converts from the timestamp st_mtime to a useful string"""
        stat_time = note_path.stat().st_mtime
        return datetime.datetime.fromtimestamp(stat_time).isoformat()

    # note_list = ['lesley-20220830.md', 'bob-20210723.md', 'harry-20221212.md']
    # data = {'notes':note_list}
    logger.debug("in api list")
    notes = sorted(
        Path(project_settings.notes_path).glob("*.md"),
        key=os.path.getmtime,
        reverse=True,
    )
    names = [note.name for note in notes]
    logger.debug("found %d notes on disk", len(names))
    data = {"notes": [{"name": note.name, "time": modified_time(note)} for note in notes]}
    logger.debug("first element: " + str(data["notes"][0]))
    # response.content_type = "application/json"
    # return dumps(data)
    return data


@app.route("/api/updateDatabase", methods=["GET"])
def update_database():
    """Updates the database with files in the currently active notes directory"""
    result, number_updated = do_scan(exclude=["crap"])
    if result == 0:
        return {"result": "success", "count": number_updated}
    else:
        return {"result": "error encountered during file scan", "updated": 0}
