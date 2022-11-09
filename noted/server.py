"""
server.py

HTTP server for the backend of the dred project
"""
import os
from pathlib import Path
from signal import signal
import signal
import sys
import threading
from functools import partial
from json import dumps
import time

from bottle import Bottle, static_file, request, jinja2_view, response

from dred.utils import create_logger, debugging
from dred.settings import load_configuration
from dred.database import find_notes_by_filename, connect_to_database, find_all_notes
from dred.notes import Note
from dred.searches import do_scan
import dred.settings as settings

logger = create_logger(__name__, debugging=True)
project_settings = load_configuration()

PORT = 5823
SERVER_URL = f"http://localhost:{PORT}/"
STATIC_JS = "./static/js"
logger.debug(f"current working directory: {Path.cwd()}")
view = partial(jinja2_view, template_lookup=["./templates/"])

app = Bottle()

###############################################################
# STATIC ROUTES
###############################################################


@app.route(r"/static/js/<filepath:re:.*\.js>")
def js(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/vs/base/worker/<filepath:re:.*\.js>")
def worker(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/vs/base/common/worker/<filepath:re:.*\.js>")
def common_worker(filepath):
    return static_file(filepath, root=STATIC_JS)


@app.route(r"/static/css/<filepath:re:.*\.css>")
def css(filepath):
    return static_file(filepath, root="./static/css")


@app.route(r"/static/icons/<filepath:re:.*\.ico>")
def icons(filepath):
    return static_file(filepath, root="./static/icons")


@app.route(
    r"/static/base/browser/ui/codicons/codicon/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>"
)
def codicon(filepath):
    return static_file(filepath, root="./static/font")


@app.route(r"/static/font/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>")
def font(filepath):
    return static_file(filepath, root="./static/font")


@app.route(r"/vs/editor/editor.main.css")
def editor_css():
    return static_file("editor.main.css", root="./static/css")


###############################################################
# PAGE ROUTES
###############################################################

CONFIG_FILE_EXISTS = settings.config_file_exists()


@app.route("/noconfig")
@view("noconfig.html")
def no_config() -> dict[str, bool]:
    """Called to report absent configuration file."""
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/")
@app.route("/home")
@view("home.html")
def home() -> dict[str, bool]:
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/about")
@view("about.html")
def about() -> dict[str, bool]:
    return dict(config_found=CONFIG_FILE_EXISTS)


@app.route("/editor")
@view("editor.html")
def editor() -> dict[str, bool]:
    return dict(config_found=CONFIG_FILE_EXISTS)


def terminal_process(delay=2):
    time.sleep(delay)
    print("server shutting down", file=sys.stderr)
    signal.raise_signal(signal.SIGINT)


@app.route("/terminate")
@view("terminate.html")
def terminate() -> dict[str, bool]:
    t = threading.Thread(target=terminal_process, daemon=True)
    t.start()
    return dict(config_found=CONFIG_FILE_EXISTS)


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


@app.route("/api/create/", method="post")
def create():
    """Creates a new note with the provided parameters"""
    filename: str = request.params["filename"]  # type:ignore
    keywords = request.params["keywords"]  # type:ignore
    present = request.params["present"]  # type:ignore
    speakers = request.params["speakers"]  # type:ignore
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
    return {"result": f"success writing ({len(text)} chars)", "filename": filename}


@app.route("/api/findfiles/", method="post")
def find_files():
    """Returns the names of files corresponding to the provided search string"""
    key: str = str(request.params["search_string"]).lower()  # type:ignore
    logger.debug("received request to search for files starting with '%s'", key)
    if not key.endswith("*"):
        key = key + "*.md"
    file_paths = sorted(
        Path(project_settings.notes_path).glob(key), key=os.path.getmtime, reverse=True
    )
    # file_list = [file.name for file in file_paths]
    data = {i: item for i, item in enumerate(file.name for file in file_paths)}
    logger.debug("found %d files with search string: %s", len(data), key)
    response.content = "application/json"  # type:ignore
    return data


@app.route("/api/findFilesInDatabase/", method="post")
def find_files_in_database():
    """Returns the names of files from the database corresponding to the provided search string"""
    key: str = str(request.params["search_string"]).lower()  # type:ignore
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
    response.content = "application/json"  # type:ignore
    return data


@app.route("/api/get/", method="post")
def get():
    """Return the note matching the request to the frontend"""
    filename = request.params["filename"]  # type:ignore
    logger.debug("get: received request for filename: %s", filename)
    note_path = Path(project_settings.notes_path).joinpath(filename)
    try:
        with open(note_path, "r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        logger.warning("unable to find file named: %s", filename)
        text = "ERROR:NOT FOUND"
    response.content_type = "application/json"
    data = {"text": text}
    return dumps(data)


@app.route("/api/fullPath/", method="post")
def full_path():
    """Return the fully qualified path to the caller
    Assumes that a name with separators is fully qualified.
    """
    name: str = request.params["filename"]  # type:ignore
    if "/" in name or "\\" in name:
        return {"path": name}
    else:
        return {"path": Path(project_settings.notes_path).joinpath(name).as_posix()}


@app.route("/api/store/", method="post")
def store():
    """Called when data is to be stored on disk, after a change."""
    text: str = request.params["text"]  # type:ignore
    filename: str = request.params["filename"]  # type:ignore
    if not filename:
        logger.debug("no file to write")
        return {"result": "no file to write"}
    try:
        with open(filename, mode="w", encoding="utf-8") as file:
            # logger.debug("file: %s storing: %s", filename, text)
            logger.debug("writing %d bytes to file: %s", len(text), filename)
            file.write(text)
        return {"result": f"success writing file {filename} ({len(text)} chars)"}
    except IOError:
        logger.debug("error encountered while attempting to write file: %s", filename)
        return {"result": "error writing file"}


@app.route("/api/list")
def list_notes():
    """Returns a list of notes stored in the database"""
    # note_list = ['lesley-20220830.md', 'bob-20210723.md', 'harry-20221212.md']
    # data = {'notes':note_list}
    logger.debug("in api list")
    notes = sorted(
        Path(project_settings.notes_path).glob("*.md"),
        key=os.path.getmtime,
        reverse=True,
    )
    data = {"notes": [note.name for note in notes]}
    response.content_type = "application/json"
    return dumps(data)


@app.route("/api/updateDatabase", method="GET")
def update_database():
    """Updates the database with files in the currently active notes directory"""
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
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()


def stop_server() -> None:
    app.close()
