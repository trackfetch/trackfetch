# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-format metadata taggers and the format factory."""

from pathlib import Path

from ..config_pkg.constants import DEFAULT_LYRICS_TYPE
from ..enums import AudioFormat
from ..protocols import Tagger
from .m4a import M4aTagger, add_m4a_metadata
from .mp3 import Mp3Tagger, add_mp3_metadata
from .opus import OpusTagger, add_opus_metadata

_TAGGERS = {
    AudioFormat.MP3: Mp3Tagger,
    AudioFormat.M4A: M4aTagger,
    AudioFormat.OPUS: OpusTagger,
}


def get_tagger(audio_format: AudioFormat) -> Tagger:
    """Return a :class:`Tagger` implementation for one audio format."""
    return _TAGGERS[AudioFormat(audio_format)]()


def add_metadata(
    audio_path: Path,
    cover_path: Path,
    metadata: dict,
    lyrics=None,
    lyrics_type=DEFAULT_LYRICS_TYPE,
):
    """Tag a file, choosing the format from its suffix (legacy entry point)."""
    try:
        audio_format = AudioFormat(audio_path.suffix.lstrip(".").lower())

    except ValueError:
        # The historical fallback for an unexpected suffix was MP3.
        audio_format = AudioFormat.MP3

    get_tagger(audio_format).tag(
        audio_path,
        cover_path,
        metadata,
        lyrics,
        lyrics_type,
    )


__all__ = [
    "M4aTagger",
    "Mp3Tagger",
    "OpusTagger",
    "add_m4a_metadata",
    "add_metadata",
    "add_mp3_metadata",
    "add_opus_metadata",
    "get_tagger",
]
