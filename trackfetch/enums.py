# SPDX-License-Identifier: GPL-3.0-or-later
"""String-based enums shared across the pipeline.

The values intentionally equal the historical literal strings so the config
file, the CLI and done.txt keep working unchanged.
"""

from enum import Enum


class AudioFormat(str, Enum):
    """Supported output audio formats."""

    MP3 = "mp3"
    M4A = "m4a"
    OPUS = "opus"


class MusicSource(str, Enum):
    """Music download sources."""

    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
