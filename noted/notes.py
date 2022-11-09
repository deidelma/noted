"""
Provides the data models used for storing state in the editor.

Uses a subset of markdown:

First line must be a top level header (i.e., # something... ).
Metadata (<? ... ?>) must be found between the first line and the text
Everything after the last ?> is considered the body of the note.
Sections are demarcated based on second level headers (i.e, ## something... ).
"""
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel
from dred.settings import load_configuration

project_settings = load_configuration()

logger = logging.getLogger(__name__)


class OverwriteExistingNoteError(IOError):
    """Raised when an attempt is made ot overwrite an existing file."""


class Metadata(BaseModel):
    """Holds the metadata associated with note"""

    title: str = ""
    keywords: list[str] = []
    present: list[str] = []
    speakers: list[str] = []
    timestamp: datetime = datetime.now


KEYWORD_PATTERN = re.compile(r"^<\?.*keywords?:(.*)\?>$")
SPEAKER_PATTERN = re.compile(r"^<\?.*speakers?:(.*)\?>$")
PRESENT_PATTERN = re.compile(r"^<\?.*present:(.*)\?>$")


def extract_match(match: re.Match[str]) -> list[str]:
    """Returns a clean version of the matched string"""
    return match.group(1).strip().replace(";", ",").replace(", ", ",").split(",")


def parse_filename(filename: str) -> tuple[str, str, str]:
    """
    Extract the components of a filepath, assumed to be in the form: prefix-20220201-postfix

    Args:
        filename (str): The filepath to be parsed.

    Returns: A tuple of strings [prefix, date, postfix].

    """
    filename = os.path.basename(filename)
    if filename.endswith(".md"):
        filename = filename[:-3]
    date_pattern = re.compile(r"(\d\d\d\d\d\d\d\d)")
    prefix_str = date_str = postfix_str = ""
    if this_match := date_pattern.search(filename):
        date_str = this_match.group(0)
        start, finish = this_match.span()
        prefix_str = filename[0:start]
        if prefix_str.endswith("-"):
            prefix_str = prefix_str[:-1]
        postfix_str = filename[finish:]
        if postfix_str.startswith("-"):
            postfix_str = postfix_str[1:]
    return prefix_str, date_str, postfix_str


class Section:
    """Data representation of a single section within the current note."""

    def __init__(self, header: str, data: str) -> None:
        self.header = header
        self.data = data.strip()  # remove leading and following blanks

    def to_markdown(self) -> str:
        """Returns section in Markdown format.

        Returns:
            str: The section rendered as markdown.
        """
        return f"## {self.header}\n\n{self.data.strip()}"


class Note:
    """Data representation of the note currently being edited."""

    def __init__(
        self,
        page_header: str,
        filename: str = "",
        keywords: list[str] | None = None,
        present: list[str] | None = None,
        speakers: list[str] | None = None,
        timestamp: datetime = datetime.now(),
    ) -> None:
        self.page_header = page_header
        if filename:
            self.filename = filename
            _, date_str, _ = parse_filename(filename)
            self.date = date_str
        else:
            today_date = date.today()
            date_str = (
                self.date
            ) = f"{today_date.year:4}{today_date.month:02}{today_date.day:02}"
            self.filename = f"{date_str}"
        if keywords:
            self.keywords = keywords
        else:
            self.keywords: list[str] = []
        if present:
            self.present = present
        else:
            self.present: list[str] = []
        if speakers:
            self.speakers = speakers
        else:
            self.speakers: list[str] = []

        self.timestamp = timestamp

        self.sections: dict[str, Section] = {}
        self._body = ""

    @property
    def body(self) -> str:
        """Provide a representation of this note in text"""
        return self.to_markdown()

    @body.setter
    def body(self, value: str) -> None:
        """Sets the representation of this note to provided value"""
        self._body = value

    def remove_section(self, heading: str) -> None:
        """Removes the section with the provided heading, if it exists"""
        if len(self.sections) == 0:
            logger.warning("attempt to remove from empty section list")
            return
        if heading in self.sections:
            del self.sections[heading]
            logger.debug("removed section: %s", heading)
        else:
            logger.warning("attempt to remove non-existent section: %s", heading)

    def create_section(self, heading: str, data: str) -> None:
        """Object holds section information.
        Sections are defined by ## heading."""
        if heading:
            this_section = Section(heading, data)
            self.sections[heading] = this_section
            logger.debug("created section: %s", heading)
        else:
            logger.warning("attempt to create section with empty header")

    def to_markdown(self) -> str:
        """Returns note in Markdown format.

        Returns:
            str: The note rendered as markdown.
        """
        lines: list[str] = []
        header_str = f"# {self.page_header}\n"
        lines.append(header_str)
        if len(self.keywords) > 0:
            lines.append(f"<? keywords: {', '.join(self.keywords)} ?>")
        if len(self.present) > 0:
            lines.append(f"<? present: {', '.join(self.present)} ?>")
        if len(self.speakers) > 0:
            lines.append(f"<? speakers: {', '.join(self.speakers)} ?>")
        lines.append("")
        logger.debug("note data structure has %d sections.", len(self.sections))
        for (heading, value) in self.sections.items():
            # for heading in self.sections:
            logger.debug("Converting section:%s to markdown", heading)
            lines.append(value.to_markdown())
            lines.append("")
        return "\n".join(lines)

    def from_markdown(self, markdown: str) -> None:
        """
        Attempts to parse the provided markdown data, which must be in
        dred specific format.  Replaces the current values in this
        note.

        Args:
            markdown (str): The input data to update this note.
        """
        temp = self.__class__.create_note_from_markdown(markdown)
        self.copy_note(temp)

    def copy_note(self, other: "Note") -> None:
        """
        Copy the values of another note to this one.
        This is a deep copy.

        Args:
            other (Note): The note to copy.
        """
        self.page_header = other.page_header
        self.keywords = other.keywords.copy()
        self.present = other.present.copy()
        self.speakers = other.speakers.copy()
        for header in other.sections:
            self.create_section(header, other.sections[header].data)
        self.body = other.body

    def write_file(
        self, filename: str | Path | None = None, overwrite: bool = False
    ) -> None:
        """
        Write file to disc using provided fully qualified< filename.
        If no filename provided, uses self.filename.
        If overwrite is True, will silently overwrite an existing file.
        If overwrite is False, raise OverwriteExistingNoteError
        Args:
            filename:
            overwrite: If True, silently overwrite.
        """

        if not filename:
            filename = self.filename
        path = Path(filename)

        if not overwrite and path.exists():
            raise OverwriteExistingNoteError(f"Attempt to overwrite {self.filename}")

        data = self.to_markdown()
        with open(path, mode="w", encoding="utf-8") as file:
            file.write(data)

    #################################################################################
    #
    #   class methods
    #
    #################################################################################

    @classmethod
    def create_note_from_markdown(cls, markdown: str) -> "Note":

        """Factory method creating a note object from Markdown.

        Assumes that the note is properly formatted to allow for one pass analysis.

        First line should be a level 1 title: e.g., '# something'
        Metadata should follow: e.g., <? keywords: a, b, c ?>
        All sections follow the metadata. Each is preceded by a level 2 title: e.g., '## a title'

        Args:
            markdown: the Markdown text to be parsed

        Returns:
            A note based on the data in markdown_str
        """

        def parse_metadata(temp: "Note", data_line: str):
            if this_match := KEYWORD_PATTERN.match(data_line):
                temp.keywords.extend(extract_match(this_match))
            elif this_match := SPEAKER_PATTERN.match(data_line):
                temp.speakers.extend(extract_match(this_match))
            elif this_match := PRESENT_PATTERN.match(data_line):
                temp.present.extend(extract_match(this_match))

        header = ""
        note = Note(header)
        in_section = False
        data: list[str] = []
        section_header: str = ""
        # section: Section | None = None
        lines: list[str] = markdown.split("\n")
        body_lines: list[str] = []
        for this_line in lines:
            line = this_line.strip()
            if line.startswith("# "):
                note.page_header = line[2:]
            elif line.startswith("<?"):
                # check for keywords, present, speaker
                parse_metadata(note, line)
            elif line.startswith("## "):
                if in_section:
                    text = "\n".join(data)
                    note.sections[section_header] = Section(section_header, text)
                    section_header = line[2:].strip()
                    data = []
                else:
                    in_section = True  # starting list of sections
                    section_header = line[2:].strip()
                    data = []
            elif in_section:
                data.append(line)
            body_lines.append(line)

        # need to clean up last section
        if section_header:
            note.sections[section_header] = Section(section_header, "\n".join(data))
        note.body = "\n".join(body_lines)
        return note

    @classmethod
    def extract_metadata_from_file_path(cls, path: Path) -> Metadata:
        """
        Given a path to a file, parses the metadata based on the filepath.
        Calls extract_metadata_from_text to add the metadata from file itself.

        :param path: The path to the note file on disk.
        :return: A note object or None if the path is not a valid note.
        """
        result = Metadata()
        name = path.stem
        if "-" in name:
            items = name.split("-")
        else:
            items = name.split(" ")
        if len(items):
            date_data: list[str] = []
            kw_data: list[str] = []
            if items[0].isnumeric():
                # assume it's a date
                date_data.append(items[0])
            else:
                # it's a keyword
                result.keywords.append(items[0])  # pylint: disable=no-member
            # check the rest of the items
            # assumes that all date data is together and anything following is a data
            for item in items[1:]:
                if item.isnumeric():
                    date_data.append(item)
                else:
                    kw_data.append(item)
            file_date = "".join(
                date_data
            ).strip()  # accumulate all numeric components of the date
            last = " ".join(kw_data).strip()  # data separated by spaces
            result.keywords.append(file_date)  # pylint: disable=no-member
            if last:
                result.keywords.append(last)
        result.timestamp = datetime.fromtimestamp(path.stat().st_mtime)
        return result

    @classmethod
    def load_file(cls, file_path: Path) -> "Note":
        """
        Loads a note from the operating system.
        Currently, supports a limited subset of Markdown.

        Does not check the validity of the data loaded from the file.

        Args:
            file_path: a pathlib.Path for the file

        Raises:
            FileNotFoundError if file_path does not exist

        Returns: A Note object containing the data stored in the file.
        """
        meta = Note.extract_metadata_from_file_path(file_path)
        with open(file_path, encoding="utf-8") as file:
            data = file.read()
        note = Note.create_note_from_markdown(data)
        for kw in meta.keywords:
            if kw and kw not in note.keywords:
                note.keywords.append(kw)
        # note.keywords.extend(meta.keywords)
        note.timestamp = meta.timestamp
        return note
