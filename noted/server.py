"""
server.py

HTTP server for the backend of the noted project
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

from noted.utils import create_logger, debugging
from noted.settings import load_configuration
from noted.database import find_notes_by_filename, connect_to_database, find_all_notes
from noted.notes import Note
from noted.searches import do_scan
import noted.settings as settings

logger = create_logger(__name__)
project_settings = load_configuration()

PORT = 5823
SERVER_URL = f"http://localhost:{PORT}/"
STATIC_PATH = Path(__file__).absolute().parent.joinpath("static")
TEMPLATES_PATH = Path(__file__).absolute().parent.joinpath("templates")
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
    return static_file(filepath, root=STATIC_CSS)


@app.route(r"/static/icons/<filepath:re:.*\.ico>")
def icons(filepath):
    return static_file(filepath, root=STATIC_ICONS)


@app.route(
    r"/static/base/browser/ui/codicons/codicon/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>"
)
def codicon(filepath):
    return static_file(filepath, root=STATIC_FONTS)


@app.route(r"/static/font/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>")
def font(filepath):
    return static_file(filepath, root=STATIC_FONTS)


@app.route(r"/vs/editor/editor.main.css")
def editor_css():
    return static_file("editor.main.css", root=STATIC_CSS)


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
    decoded = request.params.decode(encoding='utf-8')
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
        "text": text,
    }


@app.route("/display")
@view("display.html")
def display() -> dict[str, bool | str]:
    decoded = request.params.decode('utf-8')
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
    print("server shutting down", file=sys.stderr)
    remove_crap()
    update_database_before_exiting()
    time.sleep(delay)
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
    logger.debug("received request to create a note")
    decoded = request.params.decode(encoding='utf-8')
    filename = decoded['filename']
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


@app.route("/api/findfiles", method="post")
def find_files():
    """Returns the names of files corresponding to the provided search string"""
    logger.debug("received request to find files on disk based on a search")
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
    response.content = JSON_TYPE  # type: ignore
    return data


@app.route("/api/findFilesInDatabase/", method="post")
def find_files_in_database():
    """Returns the names of files from the database corresponding to the provided search string"""
    logger.debug("received request to find files in the database based on a search")
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
    response.content = JSON_TYPE  # type:ignore
    return data


@app.route("/api/get/", method="post")
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


@app.route("/api/fullPath/", method="post")
def full_path():
    """Return the fully qualified path to the caller
    Assumes that a name with separators is fully qualified.
    """
    decoded = request.params.decode('utf-8')
    name: str = decoded["filename"]  # type:ignore
    if "/" in name or "\\" in name:
        return {"path": name}
    else:
        return {"path": Path(project_settings.notes_path).joinpath(name).as_posix()}


@app.route("/api/store/", method="post")
def store():
    """Called when data is to be stored on disk, after a change."""
    logger.debug("received request to store a file on disk")
    decoded = request.params.decode('utf-8')
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
    logger.debug("in list_notes_by_stem")
    stem = request.params["search_string"]  # type: ignore
    logger.debug("received request to list files based on stem: %s", stem)
    notes = sorted(
        Path(project_settings.notes_path).glob(f"{stem}*.md"),
        key=os.path.getmtime,
        reverse=True,
    )
    data = {"notes": [note.name for note in notes]}
    response.content_type = JSON_TYPE
    return dumps(data)


@app.route("/api/list")
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


@app.route("/api/updateDatabase", method="GET")
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
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()


def stop_server() -> None:
    app.close()
