"""
Tests for watcher.py
"""
from noted.watcher import valid_note


def test_valid_note():
    assert valid_note("bob.md")
    assert valid_note("usr/bin/alph.md")
    assert not valid_note("crap.md")
    assert not valid_note("bob.com")
    assert not valid_note("crap_crap.md")
