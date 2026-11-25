# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line parsing and entry point."""

import argparse
import configparser
import contextlib
import io
import sys
from pathlib import Path

from .config_pkg.config import config_str_value
from .config_pkg.constants import (
    AUDIO_FORMATS,
    DEFAULT_AUDIO_QUALITY,
    LYRICS_TYPES,
    VERSION,
)
from .config_pkg.settings import apply_config, load_config
from .core.runner import collect_sources, run
from .ui import colors
from .ui.helpfmt import TrackFetchHelpFormatter
from .ui.themes import find_theme_file, load_theme_file

CONFIG_PATHS = (
    "--config PATH",
    "$TRACKFETCH_CONFIG",
    "./trackfetch.ini",
    "$XDG_CONFIG_HOME/trackfetch/trackfetch.ini",
    "~/.config/trackfetch/trackfetch.ini",
    "~/.trackfetch.ini",
)

EPILOG = "\n".join(
    (
        "Config:",
        "Lookup order, first found wins:",
        *(f"  {path}" for path in CONFIG_PATHS),
        "",
        "A flag wins over the config file, and the config file wins over "
        "the built-in default.",
        "",
        "Examples:",
        "  trackfetch songs.txt",
        "  trackfetch --track 'Daft Punk - One More Time'",
        "  trackfetch -o ~/Music -f m4a songs.txt",
        "  trackfetch --list-sources --color never",
    )
)


def _add_input_args(group):
    group.add_argument(
        "inputs",
        nargs="*",
        metavar="INPUT",
        help=(
            "Text file with Artist - Title, "
            "or an inline 'Artist - Title' track"
        ),
    )

    group.add_argument(
        "--track",
        action="append",
        nargs="+",
        metavar="ARTIST - TITLE",
        help=(
            "Track to download inline, "
            "can be given several times"
        ),
    )


def _add_output_args(group):
    group.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory "
            "(overrides the config file, "
            "defaults to the current directory)"
        ),
    )


def _add_audio_args(group):
    group.add_argument(
        "-f",
        "--format",
        choices=list(AUDIO_FORMATS),
        default=None,
        help="Audio format (default: mp3)",
    )

    group.add_argument(
        "--audio-quality",
        type=int,
        choices=range(10),
        metavar="0-9",
        default=None,
        help=(
            "MP3 VBR quality: 0 is best/largest, 9 is smallest "
            f"(default: {DEFAULT_AUDIO_QUALITY})"
        ),
    )

    group.add_argument(
        "--title-only",
        action="store_true",
        default=None,
        help="Use only title in filename (default: off)",
    )


def _add_metadata_args(group):
    group.add_argument(
        "-s",
        "--metadata-sources",
        default=None,
        metavar="SOURCES",
        help=(
            "Comma-separated metadata priority, for example "
            "'deezer,itunes,musicbrainz' or 'none' "
            "(default: itunes). If every source misses, free fallbacks "
            "deezer and musicbrainz are tried unless disabled"
        ),
    )

    group.add_argument(
        "--music-sources",
        default=None,
        metavar="SOURCES",
        help=(
            "Comma-separated music priority, for example "
            "'soundcloud,youtube' or 'youtube' "
            "(default: youtube,soundcloud)"
        ),
    )

    group.add_argument(
        "--disable-sources",
        default=None,
        metavar="SOURCES",
        help=(
            "Comma-separated sources to disable, "
            "for example 'spotify,youtube'"
        ),
    )

    group.add_argument(
        "--provider-opt",
        action="append",
        default=None,
        metavar="NAME.KEY=VALUE",
        help=(
            "Provider-specific setting, for example "
            "--provider-opt itunes.country=ua"
        ),
    )

    group.add_argument(
        "--match-threshold",
        type=float,
        default=None,
        metavar="SCORE",
        help="Minimum overall match score, 0.0-1.0 (default: 0.6)",
    )

    group.add_argument(
        "--title-threshold",
        type=float,
        default=None,
        metavar="SCORE",
        help="Minimum title similarity, 0.0-1.0 (default: 0.8)",
    )


def _add_source_args(group):
    group.add_argument(
        "--youtube",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="youtube_enabled",
        help=(
            "Download from YouTube and use its thumbnails; disable it to "
            "use SoundCloud only (default: on)"
        ),
    )

    group.add_argument(
        "--soundcloud",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="soundcloud_enabled",
        help=(
            "Enable SoundCloud as a music source. It is tried after YouTube "
            "by default, when --soundcloud-trigger allows it "
            "(default: on)"
        ),
    )


def _add_trigger_args(group):
    group.add_argument(
        "--soundcloud-trigger",
        choices=("age", "blocked", "age-or-missing", "any"),
        default=None,
        metavar="WHEN",
        help=(
            "When to try SoundCloud: age (age restriction only, default), "
            "blocked (age restriction or a YouTube bot/login wall), "
            "age-or-missing (blocked, plus no confident YouTube match) or "
            "any (any failed search or download)"
        ),
    )

    group.add_argument(
        "--soundcloud-ambiguous",
        choices=("skip", "best"),
        default=None,
        metavar="MODE",
        help=(
            "Several equally good SoundCloud results: skip them (default) "
            "or take the highest scoring one without asking, which is what "
            "non-interactive runs need"
        ),
    )


def _add_soundcloud_threshold_args(group):
    group.add_argument(
        "--soundcloud-min-score",
        type=float,
        default=None,
        metavar="SCORE",
        help=(
            "Minimum SoundCloud match score before downloading without "
            "asking, 0.0-1.0 (default: 0.75)"
        ),
    )

    group.add_argument(
        "--soundcloud-min-margin",
        type=float,
        default=None,
        metavar="SCORE",
        help=(
            "Score gap required between the best two SoundCloud results "
            "before picking one automatically, 0.0-1.0 (default: 0.08)"
        ),
    )


def _add_list_and_credentials_args(group):
    group.add_argument(
        "--list-sources",
        action="store_true",
        default=None,
        help="List available metadata sources and exit",
    )

    group.add_argument(
        "--spotify-client-id",
        default=None,
        help="Spotify client ID (overrides the config file and the env)",
    )

    group.add_argument(
        "--spotify-client-secret",
        default=None,
        help="Spotify client secret (overrides the config file and the env)",
    )


def _add_behavior_args(group):
    group.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit",
    )

    group.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"trackfetch {VERSION}",
        help="Show the version and exit",
    )

    group.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to a config file "
            "(default: auto-detected, see below)"
        ),
    )

    group.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Delay between songs in seconds (default: 1.0)",
    )

    group.add_argument(
        "--no-logs",
        action="store_true",
        default=None,
        help=(
            "Do not read done.txt and do not write done.txt or failed.txt; "
            "progress from earlier runs is ignored (default: off)"
        ),
    )


def _add_lyrics_args(group):
    group.add_argument(
        "--lyrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="lyrics_enabled",
        help=(
            "Embed lyrics from LRCLIB into the tags: ID3 USLT/SYLT for MP3, "
            "©lyr for M4A, LYRICS for Opus. Searches by title, then relaxed "
            "queries, and ranks by title, artist and duration (default: on)"
        ),
    )

    group.add_argument(
        "--lyrics-type",
        choices=LYRICS_TYPES,
        default=None,
        help=(
            "Timed lyrics placement: inline keeps LRC timestamps in the "
            "plain lyrics tag (default), sidecar writes a separate "
            "<file>.lrc and keeps tags plain, plain writes only plain text "
            "to the tags"
        ),
    )


def _add_cache_args(group):
    group.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="cache_enabled",
        help=(
            "Reuse and update metadata-cache.json in the output directory "
            "(default: on)"
        ),
    )


def _add_appearance_args(group):
    group.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default=None,
        help=(
            "Colorize terminal output: auto (default), always or never. "
            "Color is on by default and off when output is redirected"
        ),
    )

    group.add_argument(
        "--color-theme",
        default=None,
        metavar="THEME",
        help=(
            "Color theme: cassette (default), neon-tape, mono, vinyl "
            "or a theme from themes.ini"
        ),
    )

    group.add_argument(
        "--themes-file",
        type=Path,
        default=None,
        help=(
            "Custom theme file (default: themes.ini next to the config file)"
        ),
    )


def build_parser():
    """Build the argument parser (shared with the help tests)."""
    parser = argparse.ArgumentParser(
        prog="trackfetch",
        usage="%(prog)s [OPTIONS] [INPUT ...]",
        description=(
            "Download music using free metadata sources and music providers"
        ),
        epilog=EPILOG,
        formatter_class=TrackFetchHelpFormatter,
        add_help=False,
    )

    # Python 3.14+ colors help itself when stdout is a TTY; that would clash
    # with our own theme coloring and inflate the measured widths.
    parser.color = False

    input_group = parser.add_argument_group("Input")
    output_group = parser.add_argument_group("Output")
    metadata_group = parser.add_argument_group("Metadata")
    behavior_group = parser.add_argument_group("Behavior")
    appearance_group = parser.add_argument_group("Appearance")

    _add_input_args(input_group)
    _add_output_args(output_group)
    _add_audio_args(output_group)
    _add_metadata_args(metadata_group)
    _add_source_args(metadata_group)
    _add_trigger_args(metadata_group)
    _add_soundcloud_threshold_args(metadata_group)
    _add_list_and_credentials_args(metadata_group)
    _add_behavior_args(behavior_group)
    _add_lyrics_args(behavior_group)
    _add_cache_args(behavior_group)
    _add_appearance_args(appearance_group)

    return parser


def early_color_mode(argv):
    """Read --color before parsing so -h can honor it.

    ``argparse`` prints help and exits from inside ``parse_args``, before the
    parsed value is available, so the mode has to be known up front.
    """
    for index, arg in enumerate(argv):
        if arg == "--color" and index + 1 < len(argv):
            return argv[index + 1]

        if arg.startswith("--color="):
            return arg.split("=", 1)[1]

    return colors.DEFAULT_COLOR_MODE


def _help_preparse(argv):
    """Parse only the options that decide how help itself is rendered."""
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre.add_argument("--color")
    pre.add_argument("--color-theme")
    pre.add_argument("--themes-file")
    pre.add_argument("--config", type=Path)

    try:
        with contextlib.redirect_stderr(io.StringIO()):
            options, _unknown = pre.parse_known_args(argv)

    except SystemExit:
        return None

    return options


def _warn(message):
    print(f"WARNING: {message}", file=sys.stderr)


def help_requested(argv):
    """Return whether this run only asks for help."""
    return any(arg in ("-h", "--help") for arg in argv)


def prepare_help_style(argv):
    """Apply color mode and theme before argparse renders ``-h``.

    The precedence matches the rest of the program: a flag wins over the
    config file, which wins over the built-in default. Any problem falls back
    to the default theme with a warning on stderr, so help always prints.
    """
    if not help_requested(argv):
        return

    options = _help_preparse(argv)

    if options is None:
        return

    try:
        settings, config_path = load_config(options.config)

    except (FileNotFoundError, configparser.Error) as error:
        _warn(f"Ignoring config for help output: {error}")
        settings, config_path = {}, None

    mode = (
        options.color
        or config_str_value(settings, "color")
        or colors.DEFAULT_COLOR_MODE
    )

    try:
        colors.set_color_mode(mode)

    except ValueError as error:
        _warn(f"{error}; using {colors.DEFAULT_COLOR_MODE} for help")
        colors.set_color_mode(colors.DEFAULT_COLOR_MODE)

    explicit_themes_file = (
        options.themes_file
        or config_str_value(settings, "themes_file")
    )

    try:
        theme_path = find_theme_file(explicit_themes_file, config_path)
        load_theme_file(theme_path, required=bool(explicit_themes_file))

    except (OSError, ValueError) as error:
        _warn(f"Ignoring themes for help output: {error}")

    theme = (
        options.color_theme
        or config_str_value(settings, "color_theme")
        or colors.DEFAULT_THEME
    )

    try:
        colors.set_theme(theme)

    except ValueError as error:
        _warn(f"{error}; using {colors.DEFAULT_THEME} for help")
        colors.set_theme(colors.DEFAULT_THEME)


def _fail(message):
    print(colors.error(f"ERROR: {message}"))
    raise SystemExit(1)


def _load_settings(args):
    try:
        return load_config(args.config)

    except FileNotFoundError as error:
        _fail(error)

    except configparser.Error as error:
        _fail(f"Invalid config file: {error}")


def _apply_themes(args, settings, config_path):
    explicit_themes_file = (
        args.themes_file
        or config_str_value(settings, "themes_file")
    )

    try:
        theme_path = find_theme_file(explicit_themes_file, config_path)
        load_theme_file(theme_path, required=bool(explicit_themes_file))

    except (OSError, ValueError) as error:
        _fail(error)


def _configure_run(args, parser, settings):
    try:
        apply_config(args, parser, settings)

    except ValueError as error:
        _fail(error)

    args.color = args.color or colors.DEFAULT_COLOR_MODE
    args.color_theme = args.color_theme or colors.DEFAULT_THEME
    colors.set_color_mode(args.color)

    try:
        colors.set_theme(args.color_theme)

    except ValueError as error:
        _fail(error)


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)

    except (AttributeError, ValueError):
        pass

    try:
        colors.set_color_mode(early_color_mode(sys.argv[1:]))

    except ValueError:
        pass

    prepare_help_style(sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args()
    colors.set_color_mode(args.color or colors.DEFAULT_COLOR_MODE)
    colors.set_theme(colors.DEFAULT_THEME)

    settings, config_path = _load_settings(args)
    _apply_themes(args, settings, config_path)
    _configure_run(args, parser, settings)
    args.config_path = config_path

    summary = run(settings, args)

    if summary.code or summary.exit:
        raise SystemExit(summary.code)

    return summary.code


__all__ = [
    "build_parser",
    "collect_sources",
    "early_color_mode",
    "help_requested",
    "main",
    "prepare_help_style",
]
