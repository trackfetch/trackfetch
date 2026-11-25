# SPDX-License-Identifier: GPL-3.0-or-later
"""Structural protocols for music sources and taggers.

These describe the contracts the pipeline relies on, so alternative
implementations (tests, future providers) can be substituted without
importing concrete modules. They are checked only by type checkers, never
at runtime.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    """A music source that can search and download one track."""

    name: str

    def find(self, artist: str, title: str, duration=None):
        """Return one best-match result dict, or None."""
        ...

    def download(self, url: str, temp_dir: Path, audio_format: str,
                 audio_quality=None):
        """Download audio into temp_dir; return the path or None."""
        ...


@runtime_checkable
class Tagger(Protocol):
    """Writes metadata, cover art and lyrics into a downloaded file."""

    def tag(self, audio_path: Path, cover_path: Path, metadata: dict,
            lyrics=None, lyrics_type: str = "inline"):
        """Tag one audio file in place."""
        ...
