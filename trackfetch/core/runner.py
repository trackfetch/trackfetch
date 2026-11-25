# SPDX-License-Identifier: GPL-3.0-or-later
"""The run orchestration: inputs, logs, runtime and the song loop."""

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..config_pkg.config import build_source_config, config_str_value, format_source_list
from ..config_pkg.constants import (
    CACHE_FILENAME,
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_DELAY,
    DEFAULT_FORMAT,
    LYRICS_MIN_INTERVAL,
    METADATA_PROVIDERS,
)
from ..config_pkg.settings import resolve_output
from ..core.files import append_line, parse_song, read_done, read_song_file
from ..enums import MusicSource
from ..ui import colors
from .context import RunContext


@dataclass(frozen=True)
class RunSummary:
    """Counts and exit code of one run."""

    code: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    # True when the run must end with SystemExit even for a zero code, which
    # keeps the historical ``sys.exit(0)`` for an empty song list.
    exit: bool = False


@dataclass
class SongLogs:
    """done.txt/failed.txt state shared by the song loop."""

    done: set
    done_file: object
    failed_file: object


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


def format_summary(label_text, value, role):
    """Color a summary label and value, muting zero counts."""
    value_style = role if value else "muted"
    return (
        f"{colors.paint(label_text, role, 'bold')} "
        f"{colors.paint(value, value_style)}"
    )


def run_songs(songs, logs: SongLogs, args, source_config, runtime, process_song):
    """Download every song, keeping the done.txt/failed.txt logs in sync.

    ``process_song`` is passed in so a plain ``-h`` or ``--list-sources``
    run never pays for importing the pipeline stack.
    """
    success = 0
    skipped = 0
    failed = 0

    for number, (artist, title) in enumerate(
        songs,
        start=1,
    ):
        song_key = f"{artist} - {title}"

        print()
        print(colors.frame("=" * 60))
        print(colors.progress(f"[{number}/{len(songs)}]"))
        print(colors.paint(song_key, "text", "bold"))

        if song_key in logs.done:
            print(colors.skip("SKIP: already completed"))
            skipped += 1
            continue

        ctx = RunContext(
            output=args.output,
            title_only=args.title_only,
            audio_format=args.format,
            audio_quality=args.audio_quality,
            source_config=source_config,
            runtime=runtime,
            lyrics_type=source_config.lyrics_type,
            input_artist=artist,
            input_title=title,
        )
        ok, reason = process_song(ctx, artist, title)

        if ok:
            if not args.no_logs:
                append_line(
                    logs.done_file,
                    song_key,
                )

            logs.done.add(song_key)

            if reason == "exists":
                skipped += 1

            else:
                success += 1

        else:
            if not args.no_logs:
                append_line(
                    logs.failed_file,
                    f"{song_key} | {reason}",
                )

            failed += 1

        if number < len(songs):
            time.sleep(args.delay)

    print()
    print(colors.frame("=" * 60))
    print(colors.heading("FINISHED"))
    print(format_summary("SUCCESS:", success, "success"))
    print(format_summary("SKIPPED:", skipped, "skip"))
    print(format_summary("FAILED:", failed, "error"))

    if not args.no_logs:
        print(f"{colors.label('DONE FILE:')} {colors.muted(logs.done_file)}")
        print(f"{colors.label('FAILED FILE:')} {colors.muted(logs.failed_file)}")

    return RunSummary(0, success, skipped, failed)


def _error(message):
    print(colors.error(f"ERROR: {message}"))
    return RunSummary(1)


def _apply_defaults(args, settings):
    if args.output is None:
        args.output = resolve_output(None, settings)

    if args.format is None:
        args.format = DEFAULT_FORMAT

    if args.audio_quality is None:
        args.audio_quality = DEFAULT_AUDIO_QUALITY

    if args.title_only is None:
        args.title_only = False

    if args.delay is None:
        args.delay = DEFAULT_DELAY

    if args.no_logs is None:
        args.no_logs = False


def _validate_delay(args):
    if not math.isfinite(args.delay):
        return f"Delay must be a finite number: {args.delay}"

    if args.delay < 0:
        return f"Delay must not be negative: {args.delay}"

    return None


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


def _soundcloud_status(source_config):
    trigger_labels = {
        "age": "age-restricted YouTube only",
        "blocked": "age restriction or YouTube login wall",
        "age-or-missing": "blocked, or no YouTube match",
        "any": "any failed YouTube search or download",
    }

    if source_config.primary_music_source == MusicSource.SOUNDCLOUD.value:
        return "primary" + (
            "; YouTube fallback on failure"
            if source_config.youtube_enabled
            else ""
        )

    return trigger_labels.get(
        source_config.soundcloud_trigger,
        source_config.soundcloud_trigger,
    )


def _print_settings(args, source_config, config_path):
    if config_path:
        print(f"{colors.label('Config:')} {config_path}")

    print(f"{colors.label('Output:')} {args.output}")

    print(
        f"{colors.label('Music sources:')} "
        + colors.accent(", ".join(source_config.music_sources) or "none")
    )
    print(
        f"{colors.label('Metadata sources:')} "
        + colors.accent(", ".join(source_config.metadata_sources) or "none")
    )
    print(
        f"{colors.label('YouTube artwork fallback:')} "
        + (
            colors.success("enabled")
            if source_config.youtube_enabled
            else colors.muted("disabled")
        )
    )
    print(
        f"{colors.label('Lyrics embedding:')} "
        + (
            colors.success("enabled (all formats)")
            if source_config.lyrics_enabled
            else colors.muted("disabled")
        )
    )
    print(
        f"{colors.label('SoundCloud fallback:')} "
        + (
            colors.success("enabled (" + _soundcloud_status(source_config) + ")")
            if source_config.soundcloud_enabled
            else colors.muted("disabled")
        )
    )
    print(
        f"{colors.label('SoundCloud ambiguity:')} "
        + (
            colors.success("take the best result")
            if source_config.soundcloud_ambiguous == "best"
            else colors.muted("ask on a terminal, otherwise skip")
        )
    )

    sys.stdout.flush()


def _build_runtime(args, source_config):
    from .pipeline import process_song
    from .runtime import MetadataCache, MetadataRuntime, RateLimiter

    runtime = MetadataRuntime(
        cache=(
            MetadataCache(args.output / CACHE_FILENAME)
            if source_config.cache_enabled
            else None
        ),
        limiter=RateLimiter(
            {
                name: source_config.interval(name)
                for name in METADATA_PROVIDERS
            }
            | {"lrclib": LYRICS_MIN_INTERVAL}
        ),
        spotify_args=args,
    )
    return runtime, process_song


def run(settings, args) -> RunSummary:
    """Execute one full run and return its counts and exit code."""
    try:
        source_config = build_source_config(args, settings)

    except ValueError as error:
        return _error(error)

    if args.list_sources:
        print(format_source_list(source_config))
        return RunSummary(0)

    _apply_defaults(args, settings)
    delay_error = _validate_delay(args)

    if delay_error:
        return _error(delay_error)

    try:
        sources = collect_sources(args, settings)

    except ValueError as error:
        return _error(error)

    if not sources:
        return _error(
            "No input. "
            "Pass a file or an inline 'Artist - Title' track, "
            "or set 'input' in the config file."
        )

    if args.output.exists() and not args.output.is_dir():
        return _error(f"Output path is not a directory: {args.output}")

    songs, skipped_lines = _read_songs(sources)

    if not songs:
        print(colors.warning("No songs to download."))
        return RunSummary(0, exit=True)

    songs, duplicates = _deduplicate(songs)

    if not _create_output_directory(args.output):
        return RunSummary(1)

    if not args.no_logs:
        done_file = args.output / "done.txt"
        failed_file = args.output / "failed.txt"
        done = read_done(done_file)
    else:
        done_file = None
        failed_file = None
        done = set()

    _print_input_report(songs, duplicates, done, args.no_logs, skipped_lines)
    _print_settings(args, source_config, getattr(args, "config_path", None))

    runtime, process_song = _build_runtime(args, source_config)
    logs = SongLogs(done, done_file, failed_file)
    return run_songs(
        songs,
        logs,
        args,
        source_config,
        runtime,
        process_song,
    )


__all__ = ["RunSummary", "SongLogs", "collect_sources", "run", "run_songs"]
