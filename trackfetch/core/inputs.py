# SPDX-License-Identifier: GPL-3.0-or-later
"""Input discovery, done/failed logs and output-directory setup."""

import sys
from pathlib import Path

from ..config_pkg.config import config_str_value
from ..core.files import parse_song, read_song_file
from ..ui import colors


def collect_sources(args, settings):
    """Build the ordered list of inputs: file paths and inline tracks.

    Every item is either a Path to a text file or an inline
    "Artist - Title" string.
    """
    sources = []

    config_input = config_str_value(settings, "input")

    if config_input:
        path = Path(config_input).expanduser()

        if not path.is_file():
            raise ValueError(f"Input file not found: {path}")

        sources.append(path)

    for item in args.inputs:
        path = Path(item).expanduser()

        if path.is_file():
            sources.append(path)

        elif " - " in item:
            if not parse_song(item):
                raise ValueError(
                    f"Could not parse track: {item} "
                    f"(expected 'Artist - Title')"
                )

            sources.append(item)

        else:
            raise ValueError(
                f"Input file not found: {item} "
                f"(if this is a track, use the 'Artist - Title' format)"
            )

    for group in args.track or []:
        for spec in group:
            if not parse_song(spec):
                raise ValueError(
                    f"Could not parse track: {spec} "
                    f"(expected 'Artist - Title')"
                )

            sources.append(spec)

    return sources


def _read_songs(sources):
    songs = []
    skipped_lines = []

    for source in sources:
        if isinstance(source, Path):
            file_songs, file_skipped = read_song_file(source)

            songs.extend(file_songs)

            skipped_lines.extend(
                (source, line) for line in file_skipped
            )

        else:
            song = parse_song(source)

            if song:
                songs.append(song)

    return songs, skipped_lines


def _deduplicate(songs):
    unique_songs = []
    seen_songs = set()

    for artist, title in songs:
        key = f"{artist} - {title}"

        if key in seen_songs:
            continue

        seen_songs.add(key)
        unique_songs.append((artist, title))

    return unique_songs, len(songs) - len(unique_songs)


def _create_output_directory(output):
    try:
        output.mkdir(
            parents=True,
            exist_ok=True,
        )

    except OSError as error:
        print(
            colors.error(
                f"ERROR: Cannot create output directory "
                f"{output}: {error.strerror or error}"
            )
        )

        if sys.platform == "darwin" and str(output).startswith("/home/"):
            print(
                colors.muted(
                    "On macOS home directories live under /Users; "
                    "use ~ or /Users/<name>."
                )
            )

        return False

    return True


def _print_input_report(songs, duplicates, done, no_logs, skipped_lines):
    print(f"{colors.label('Found')} {len(songs)} songs")

    if duplicates:
        print(f"{colors.label('Removed')} {duplicates} duplicate(s)")

    if not no_logs:
        print(
            f"{colors.label('Already completed:')} {len(done)} "
            f"{colors.muted('(from done.txt)')}"
        )

    if skipped_lines:
        print(
            colors.warning(
                f"WARNING: skipped {len(skipped_lines)} line(s) "
                f"that are not 'Artist - Title':"
            )
        )

        for path, line in skipped_lines[:5]:
            print(f"  {colors.muted(path)}: {line}")

        if len(skipped_lines) > 5:
            print(colors.muted(f"  ... and {len(skipped_lines) - 5} more"))
