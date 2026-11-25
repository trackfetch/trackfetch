# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup checks for external tools used by the download pipeline."""

import shutil
import sys

FFMPEG_TOOLS = ("ffmpeg", "ffprobe")


def ffmpeg_install_hint(platform=None):
    """Return the platform-specific installation command for FFmpeg."""
    platform = sys.platform if platform is None else platform

    if platform == "darwin":
        return "Install it with: brew install ffmpeg"

    if platform.startswith("linux"):
        return (
            "Install it with one of:\n"
            "  sudo apt install ffmpeg\n"
            "  sudo dnf install ffmpeg\n"
            "  sudo pacman -S ffmpeg"
        )

    if platform.startswith("win"):
        return (
            "Install it with: winget install Gyan.FFmpeg "
            "(or scoop install ffmpeg / choco install ffmpeg)"
        )

    return "Install it from https://ffmpeg.org/download.html"


def _missing_message(missing, found):
    label = (
        "ffmpeg and ffprobe"
        if len(missing) == 2
        else missing[0]
    )
    verb = "were" if len(missing) == 2 else "was"
    message = f"{label} {verb} not found"

    if found:
        message += f" ({found[0]}: found)"

    return message


def check_ffmpeg(which=None, platform=None):
    """Return ``(message, install_hint)`` when FFmpeg is unavailable."""
    which = shutil.which if which is None else which
    found = [tool for tool in FFMPEG_TOOLS if which(tool)]
    missing = [tool for tool in FFMPEG_TOOLS if tool not in found]

    if not missing:
        return None

    return _missing_message(missing, found), ffmpeg_install_hint(platform)


__all__ = ["FFMPEG_TOOLS", "check_ffmpeg", "ffmpeg_install_hint"]
