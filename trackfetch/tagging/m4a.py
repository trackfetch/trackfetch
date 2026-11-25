# SPDX-License-Identifier: GPL-3.0-or-later
"""MP4 atom tagging for M4A files."""

from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover

from ..config_pkg.constants import DEFAULT_LYRICS_TYPE
from ..images import detect_image_format
from ..lyrics import add_m4a_lyrics


def _cover_value(cover_path):
    if not cover_path.exists():
        return None

    image_data = cover_path.read_bytes()
    format_name = detect_image_format(image_data)

    # MP4 cover art supports JPEG and PNG. Embedding a GIF or WebP as
    # JPEG would mislabel the bytes, so leave it out for this format.
    if format_name == "jpeg":
        return MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)

    if format_name == "png":
        return MP4Cover(image_data, imageformat=MP4Cover.FORMAT_PNG)

    return None


class M4aTagger:
    """Write MP4 atoms, cover art and lyrics into an M4A file."""

    def tag(self, audio_path: Path, cover_path: Path, metadata: dict,
            lyrics=None, lyrics_type: str = DEFAULT_LYRICS_TYPE):
        audio = MP4(audio_path)

        fields = {
            "\xa9nam": metadata["title"],
            "\xa9ART": metadata["artist"],
            "\xa9alb": metadata["album"],
            "aART": metadata["album_artist"],
            "\xa9day": metadata["release_date"],
        }

        for key in [*fields, "trkn", "covr"]:
            if key in audio:
                del audio[key]

        for key, value in fields.items():
            if value:
                audio[key] = [str(value)]

        if metadata["track_number"]:
            audio["trkn"] = [
                (int(metadata["track_number"]), 0)
            ]

        cover = _cover_value(cover_path)

        if cover is not None:
            audio["covr"] = [cover]

        add_m4a_lyrics(audio, lyrics, lyrics_type)
        audio.save()


def add_m4a_metadata(
    m4a_path: Path,
    cover_path: Path,
    metadata: dict,
    lyrics=None,
    lyrics_type=DEFAULT_LYRICS_TYPE,
):
    M4aTagger().tag(m4a_path, cover_path, metadata, lyrics, lyrics_type)


__all__ = ["M4aTagger", "add_m4a_metadata"]
