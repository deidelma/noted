"""
server.py

HTTP server for the backend of the noted project
"""

import os
import signal
import sys
import threading
import time
from functools import partial
from json import dumps
from pathlib import Path

from bottle import Bottle, jinja2_view, redirect, request, response, static_file

import noted.settings as settings
from noted.db import (
    connect_to_database,
    find_all_notes,
    search_by_file,
    search_by_keyword,
)
from noted.notes import Note
from noted.searches import do_scan
from noted.settings import load_configuration
from noted.utils import create_logger, debugging, resource_path

logger = create_logger(__name__)
project_settings = load_configuration()

PORT = 5823
SERVER_URL = f"http://localhost:{PORT}/"
STATIC_PATH = resource_path(Path(__file__).absolute().parent.joinpath("static"))
TEMPLATES_PATH = resource_path(Path(__file__).absolute().parent.joinpath("templates"))
logger.debug("Loading templates from %s", TEMPLATES_PATH.as_posix())
STATIC_JS = STATIC_PATH.joinpath("js")
STATIC_CSS = STATIC_PATH.joinpath("css")
STATIC_ICONS = STATIC_PATH.joinpath("icons")
STATIC_FONTS = STATIC_PATH.joinpath("fonts")
logger.debug("static js: %s", STATIC_JS.as_posix())
JSON_TYPE = "application/json"

view = partial(jinja2_view, template_lookup=[TEMPLATES_PATH])

app = Bottle()


###############################################################
# STATIC ROUTES
###############################################################


@app.route(r"/static/js/<filepath:re:.*\.js>")  # type: ignore
def js(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/vs/base/worker/<filepath:re:.*\.js>")  # type: ignore
def worker(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/vs/base/common/worker/<filepath:re:.*\.js>")  # type: ignore
def common_worker(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/static/css/<filepath:re:.*\.css>")  # type: ignore
def css(filepath):
    return static_file(filepath, root=STATIC_CSS)


@app.route(r"/static/icons/<filepath:re:.*\.ico>")  # type: ignore
def icons(filepath):
    return static_file(filepath, root=STATIC_ICONS)


@app.route(
    r"/static/base/browser/ui/codicons/codicon/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>"
)  # type: ignore
def codicon(filepath):
    return static_file(filepath, root=STATIC_FONTS)


@app.route(r"/static/font/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>")  #   type: ignore
def font(filepath):
    return static_file(filepath, root=STATIC_FONTS)


@app.route(r"/vs/editor/editor.main.css")  # type: ignore
def editor_css():
    return static_file("editor.main.css", root=STATIC_CSS)


###############################################################
# PAGE ROUTES
###############################################################

CONFIG_FILE_EXISTS = settings.config_file_exists()


@app.route("/noconfig") # type: ignore
@view("noconfig.html")
def no_config() -> dict[str, bool]:
    """Called to report absent configuration file."""
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/") # type: ignore
@app.route("/home") # type: ignore
@view("home.html")
def home() -> dict[str, bool]:
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/about") #  type: ignore
@view("about.html")
def about() -> dict[str, bool]:
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/editor") # type: ignore
@view("editor.html")
def editor() -> dict[str, bool]:
    decoded = request.params.decode(encoding="utf-8")
    filename = decoded.get("filename")  # type: ignore
    logger.debug("editor: received request for filename: %s", filename)
    note_path = Path(project_settings.notes_path).joinpath(filename)
    try:
        with open(note_path, "r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        logger.warning("unable to find file named: %s", filename)
        text = "ERROR:NOT FOUND"
    return {
        "config_found": CONFIG_FILE_EXISTS,
        "filename": filename,
        "text": text, # type: ignore
    }


@app.route("/display") # type: ignore
@view("display.html")
def display() -> dict[str, bool | str]:
    decoded = request.params.decode("utf-8")
    filename = decoded.get("filename")  # type: ignore
    logger.debug("get: received request for filename: %s", filename)
    note_path = Path(project_settings.notes_path).joinpath(filename)
    try:
        with open(note_path, "r", encoding="utf-8") as file:
            text = file.read()
        logger.info("loaded file: %s", note_path.as_posix())
    except FileNotFoundError:
        logger.warning("unable to find file named: %s", filename)
        text = "ERROR:NOT FOUND"
    return {
        "config_found": CONFIG_FILE_EXISTS,
        "filename": filename,
        "note_body": text,
    }


def remove_crap(stems: list[str] | None = None):
    """
    Remove files starting with the stem 'crap' or others.

    Also removes emacs backup files ending in ~
    """
    notes_path = Path(project_settings.notes_path)
    count = 0
    if stems is None:
        stems = ["crap"]
    for stem in stems:
        files = notes_path.glob(f"{stem}*.*")
        for file in files:
            file.unlink(True)
            count += 1
    # remove emacs backup files
    files = notes_path.glob("*.*~")
    for file in files:
        file.unlink(True)
        count += 1
    if count > 0:
        logger.info("removed %d crap files", count)


def update_database_before_exiting():
    result, number_updated = do_scan()
    if result != 0:
        logger.fatal(
            "fatal error: unable to scan directory %s", project_settings.notes_path
        )
        sys.exit(1)
    if number_updated > 0:
        logger.info("updated %d files before exiting", number_updated)


def terminal_process(delay=2):
    logger.info("server shutting down in %d seconds", delay)
    remove_crap()
    update_database_before_exiting()
    time.sleep(delay)
    logger.info("sending interrupt signal")
    signal.raise_signal(signal.SIGINT)


@app.route("/terminate") # type: ignore
@view("terminate.html")
def terminate() -> dict[str, bool]:
    logger.info("starting termination thread")
    t = threading.Thread(target=terminal_process, daemon=True)
    t.start()
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/config") # type: ignore
@view("config.html")
def config() -> dict[str, bool]:
    logger.info("moving to preferences page")
    return dict(
        config_found=CONFIG_FILE_EXISTS,
        notes_path=project_settings.notes_path,
        database_path=project_settings.database_path,
    ) # type: ignore


@app.route("/preferences") # type: ignore
def preferences() -> dict[str, bool]:
    decoded = request.params.decode(encoding="utf-8")
    notes_path = decoded["notesPath"]
    logger.debug("new notes path: %s", notes_path)
    database_path = decoded["databasePath"]
    logger.debug("new database path: %s", database_path)
    return redirect("/config")  # <-- need to create acceptance page


###############################################################
# API ROUTES
###############################################################


def create_list_from_word_string(word_string: str) -> list[str]:
    """
    Create a Python list from a comma separated string

    Args:
        word_string (str): the string of words sent by the front end

    Returns:
        str: the list of strings
    """
    return [x.strip() for x in word_string.split(",")]


@app.route("/api/create/", method="post") # type: ignore
def create():
    """Creates a new note with the provided parameters"""
    logger.debug("received request to create a note")
    decoded = request.params.decode(encoding="utf-8")
    filename = decoded["filename"]
    logger.info("Received filename: %s", filename)
    keywords = decoded["keywords"]  # type:ignore
    present = decoded["present"]  # type:ignore
    speakers = decoded["speakers"]  # type:ignore
    if not filename:
        return {"result": "error: no filename provided"}
    logger.debug("creating note at file: %s", filename)
    complete_filename = Path(project_settings.notes_path).joinpath(filename).as_posix()
    note = Note(
        filename=filename,
        page_header=filename,
        keywords=create_list_from_word_string(keywords),
        present=create_list_from_word_string(present),
        speakers=create_list_from_word_string(speakers),
    )
    text = note.to_markdown()
    # print(text)
    try:
        with open(complete_filename, mode="w", encoding="utf-8") as file:
            file.write(text)
            logger.debug("wrote %d chars to disk", len(text))
    except IOError:
        return {"result": f"error encountered while writing {filename}"}
    logger.info("created file:%s", filename)
    return {"result": f"success writing ({len(text)} chars)", "filename": filename}


@app.route("/api/findFilesInDatabase/", method="post") # type: ignore
def find_files_in_database():
    """Returns the names of files from the database corresponding to the provided search string"""
    logger.debug("received request to find files in the database based on a search")
    key: str = str(request.params["search_string"]).lower()  # type:ignore
    logger.debug("received request to search for files starting with '%s'", key)
    eng = connect_to_database()
    if key == "" or key.lower() in ["all", "*.*"]:
        note_list = find_all_notes(eng)
    else:
        note_list = search_by_file(eng, key.strip().lower())
    data = {i: item for i, item in enumerate(note.filename for note in note_list)}
    logger.debug("found %d notes in database", len(data))
    response.content = JSON_TYPE  # type:ignore
    return data


@app.route("/api/findFilesByKey/", method="post") # type: ignore
def find_files_by_key():
    """Returns the names of files from the database corresponding to the provided key"""
    logger.debug("received request to find files in the database based on a keyword")
    key: str = str(request.params["keyword"]).lower()  # type:ignore
    logger.debug("received request to search for files with keyword %s", key)
    eng = connect_to_database()
    note_list = search_by_keyword(eng, key.strip().lower())
    data = {i: item for i, item in enumerate(note.filename for note in note_list)}
    logger.debug("found %d notes in database", len(data))
    response.content = JSON_TYPE  # type:ignore
    return data


@app.route("/api/get/", method="post") # type: ignore
def get():
    """Return the note matching the request to the frontend"""
    logger.debug("received request to retrieve a file")
    filename = request.params["filename"]  # type:ignore
    logger.debug("get: received request for filename: %s", filename)
    note_path = Path(project_settings.notes_path).joinpath(filename)
    try:
        with open(note_path, "r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        logger.warning("unable to find file named: %s", filename)
        text = "ERROR:NOT FOUND"
    response.content_type = JSON_TYPE
    data = {"text": text}
    return dumps(data)


@app.route("/api/fullPath/", method="post") # type: ignore
def full_path():
    """Return the fully qualified path to the caller
    Assumes that a name with separators is fully qualified.
    """
    decoded = request.params.decode("utf-8")
    name: str = decoded["filename"]  # type:ignore
    if "/" in name or "\\" in name:
        return {"path": name}
    else:
        return {"path": Path(project_settings.notes_path).joinpath(name).as_posix()}


@app.route("/api/store/", method="post") #  type: ignore
def store():
    """Called when data is to be stored on disk, after a change."""
    logger.debug("received request to store a file on disk")
    decoded = request.params.decode("utf-8")
    text: str = decoded["text"]  # type:ignore
    filename: str = decoded["filename"]  # type:ignore
    if not filename:
        logger.debug("no file to write")
        return {"result": "no file to write"}
    try:
        with open(filename, mode="w", encoding="utf-8") as file:
            # logger.debug("file: %s storing: %s", filename, text)
            logger.debug("writing %d bytes to file: %s", len(text), filename)
            file.write(text)
        logger.debug("stored file: %s", filename)
        return {"result": f"success writing file {filename} ({len(text)} chars)"}
    except IOError:
        logger.debug("error encountered while attempting to write file: %s", filename)
        return {"result": "error writing file"}


@app.route("/api/stem", method=["get", "post"])  # type: ignore
def list_notes_by_stem():
    """Returns a list of notes on the disk based on the stem"""
    stem = request.params["search_string"].lower()  # type: ignore
    logger.debug(
        "searching path: %s for search string: %s",
        project_settings.notes_path,
        f"{stem}*.md",
    )
    notes = sorted(
        Path(project_settings.notes_path).glob(f"{stem}*.md"),
        key=os.path.getmtime,
        reverse=True,
    )
    data = {"notes": ",".join([note.name for note in notes])}
    logger.debug(f"{data}")
    response.content_type = JSON_TYPE
    return dumps(data)


@app.route("/api/list") # type: ignore
def list_notes():
    """Returns a list of notes on the disk"""
    logger.debug("received request to list files on disk")
    # note_list = ['lesley-20220830.md', 'bob-20210723.md', 'harry-20221212.md']
    # data = {'notes':note_list}
    logger.debug("in api list")
    notes = sorted(
        Path(project_settings.notes_path).glob("*.md"),
        key=os.path.getmtime,
        reverse=True,
    )
    data = {"notes": [note.name for note in notes]}
    response.content_type = JSON_TYPE
    return dumps(data)


@app.route("/api/updateDatabase") # type: ignore
def update():
    """Updates the database with files in the currently active notes directory"""
    logger.debug("received request to update the database")
    result, number_updated = do_scan(exclude=["crap"])
    if result == 0:
        return {"result": "success", "count": number_updated}
    else:
        return {"result": "error encountered during file scan", "updated": 0}


def serve():
    """Run the server"""
    # print(f"debugging():{debugging()}")
    app.run(host="localhost", port=PORT, quiet=not debugging(), debug=debugging())  # type: ignore


def launch_server():
    """Launch the server in its own thread."""
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()


def stop_server() -> None:
    """Stop the server."""
    app.close()
