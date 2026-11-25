# SPDX-License-Identifier: GPL-3.0-or-later
"""Downloading a SoundCloud track through yt-dlp.

The pipeline normally injects the shared yt-dlp downloader; this module gives
the SoundCloud source a default implementation of its ``download`` method.
"""

from pathlib import Path


def download_soundcloud_audio(
    url: str,
    temp_dir: Path,
    audio_format: str = "mp3",
    audio_quality=None,
):
    """Download SoundCloud audio with the shared yt-dlp backend."""
    from ..youtube import download_audio

    return download_audio(url, temp_dir, audio_format, audio_quality)


__all__ = ["download_soundcloud_audio"]
