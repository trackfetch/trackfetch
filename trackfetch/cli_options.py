# SPDX-License-Identifier: GPL-3.0-or-later
"""Argument groups for the command-line parser."""

import argparse
from pathlib import Path

from .config_pkg.constants import (
    AUDIO_FORMATS,
    DEFAULT_AUDIO_QUALITY,
    LYRICS_TYPES,
    VERSION,
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
