# SPDX-License-Identifier: GPL-3.0-or-later
"""ID3 tagging for MP3 files."""

from pathlib import Path

import mutagen
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK

from ..config_pkg.constants import DEFAULT_LYRICS_TYPE
from ..images import image_mime_type
from ..lyrics import add_mp3_lyrics


def _write_text_tags(audio, metadata):
    audio.add(TIT2(encoding=3, text=metadata["title"]))
    audio.add(TPE1(encoding=3, text=metadata["artist"]))

    if metadata["album"]:
        audio.add(TALB(encoding=3, text=metadata["album"]))

    if metadata["album_artist"]:
        audio.add(TPE2(encoding=3, text=metadata["album_artist"]))

    if metadata["track_number"]:
        audio.add(TRCK(encoding=3, text=str(metadata["track_number"])))

    if metadata["release_date"]:
        audio.add(TDRC(encoding=3, text=str(metadata["release_date"])))


def _write_cover(audio, cover_path):
    if not cover_path.exists():
        return

    image_data = cover_path.read_bytes()
    mime = image_mime_type(image_data)

    if mime is not None:
        audio.add(
            APIC(
                encoding=3,
                mime=mime,
                type=3,
                desc="Cover",
                data=image_data,
            )
        )


class Mp3Tagger:
    """Write ID3 metadata, cover art and lyrics into an MP3 file."""

    def tag(self, audio_path: Path, cover_path: Path, metadata: dict,
            lyrics=None, lyrics_type: str = DEFAULT_LYRICS_TYPE):
        try:
            audio = ID3(audio_path)
        except (mutagen.MutagenError, OSError):
            audio = ID3()

        for tag in [
            "APIC",
            "TIT2",
            "TPE1",
            "TALB",
            "TPE2",
            "TRCK",
            "TDRC",
        ]:
            audio.delall(tag)

        _write_text_tags(audio, metadata)
        _write_cover(audio, cover_path)
        add_mp3_lyrics(audio, lyrics, lyrics_type)

        audio.save(audio_path, v2_version=3)


def add_mp3_metadata(
    mp3_path: Path,
    cover_path: Path,
    metadata: dict,
    lyrics=None,
    lyrics_type=DEFAULT_LYRICS_TYPE,
):
    Mp3Tagger().tag(mp3_path, cover_path, metadata, lyrics, lyrics_type)


__all__ = ["Mp3Tagger", "add_mp3_metadata"]
