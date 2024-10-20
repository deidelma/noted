"""Miscellaneous utility functions"""

import logging
import sys
from typing import Any
from pathlib import Path


class SingletonClass(object):
    """Based class for singleton objects"""
    instance: object

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = super(SingletonClass, cls).__new__(cls, *args, **kwargs)
        return cls.instance


DEBUGGING: bool | None = None


def debugging() -> bool:
    """Returns a boolean indicating debugging_on status"""
    if DEBUGGING:
        return DEBUGGING
    else:
        return False


def create_logger(name: str = "ROOT", debugging_on: bool = False) -> logging.Logger:
    """Creates a noted system logger"""
    global DEBUGGING

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger = logging.Logger(name=name)
    logger.addHandler(handler)
    # initialize DEBUGGING at the start of the program
    if not DEBUGGING:
        DEBUGGING = debugging_on

    debug_level = logging.DEBUG if DEBUGGING else logging.INFO
    logger.setLevel(debug_level)
    return logger


def to_boolean(value: Any) -> bool:
    """Converts a value from string to boolean but accepts boolean values."""
    if isinstance(value, str):
        return value.lower().startswith("true")
    if isinstance(value, bool):
        return value
    else:
        raise ValueError(f"unable to convert object {repr(value)} to boolean")

def resource_path(relative_path: Path) -> Path:
    try:
        base_path = Path(sys._MEIPASS) # type: ignore
    except Exception:
        base_path = Path(".")

    return base_path.joinpath(relative_path)

