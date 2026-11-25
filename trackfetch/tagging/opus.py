# SPDX-License-Identifier: GPL-3.0-or-later
"""Vorbis-comment tagging for Opus files."""

import base64
from pathlib import Path

from mutagen.flac import Picture
from mutagen.oggopus import OggOpus

from ..config_pkg.constants import DEFAULT_LYRICS_TYPE
from ..images import image_mime_type
from ..lyrics import add_opus_lyrics


def _cover_value(cover_path):
    if not cover_path.exists():
        return None

    image_data = cover_path.read_bytes()
    mime = image_mime_type(image_data)

    if mime is None:
        return None

    picture = Picture()
    picture.type = 3
    picture.mime = mime
    picture.desc = "Cover"
    picture.data = image_data
    return base64.b64encode(picture.write()).decode("ascii")


class OpusTagger:
    """Write Vorbis comments, cover art and lyrics into an Opus file."""

    def tag(self, audio_path: Path, cover_path: Path, metadata: dict,
            lyrics=None, lyrics_type: str = DEFAULT_LYRICS_TYPE):
        audio = OggOpus(audio_path)

        fields = {
            "TITLE": metadata["title"],
            "ARTIST": metadata["artist"],
            "ALBUM": metadata["album"],
            "ALBUMARTIST": metadata["album_artist"],
            "TRACKNUMBER": metadata["track_number"],
            "DATE": metadata["release_date"],
        }

        for key in [*fields, "METADATA_BLOCK_PICTURE"]:
            if key in audio:
                del audio[key]

        for key, value in fields.items():
            if value:
                audio[key] = str(value)

        cover = _cover_value(cover_path)

        if cover is not None:
            audio["METADATA_BLOCK_PICTURE"] = cover

        add_opus_lyrics(audio, lyrics, lyrics_type)
        audio.save()


def add_opus_metadata(
    opus_path: Path,
    cover_path: Path,
    metadata: dict,
    lyrics=None,
    lyrics_type=DEFAULT_LYRICS_TYPE,
):
    OpusTagger().tag(opus_path, cover_path, metadata, lyrics, lyrics_type)


__all__ = ["OpusTagger", "add_opus_metadata"]
