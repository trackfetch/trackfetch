# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line parsing and entry point."""

import argparse
import configparser
import contextlib
import io
import sys
from pathlib import Path

from .cli_options import (
    _add_appearance_args,
    _add_audio_args,
    _add_behavior_args,
    _add_cache_args,
    _add_input_args,
    _add_list_and_credentials_args,
    _add_lyrics_args,
    _add_metadata_args,
    _add_output_args,
    _add_soundcloud_threshold_args,
    _add_source_args,
    _add_trigger_args,
)
from .config_pkg.config import config_str_value
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
