# SPDX-License-Identifier: GPL-3.0-or-later
"""Themeable ANSI color output.

Four themes are built in. The default is ``cassette``. Color is emitted only
for an interactive terminal; redirected output, dumb terminals and runs with
``NO_COLOR`` set stay plain. ``--color`` can force color on or off, and
``--color-theme`` selects a palette.
"""

import os
import sys

from .palettes import THEMES

_RESET = "\x1b[0m"
_ATTRS = {
    "bold": 1,
    "dim": 2,
    "underline": 4,
}

# Roles: text, accent, accent_bright, progress, success, warning, error, skip,
# muted, frame, plus the help roles heading, prog, flag, metavar, choices,
# default and dim. Each role has a 16-color, 256-color and truecolor value.
DEFAULT_THEME = "cassette"
DEFAULT_COLOR_MODE = "auto"
_COLOR_MODES = ("auto", "always", "never")
HELP_ROLES = (
    "heading",
    "prog",
    "flag",
    "metavar",
    "choices",
    "default",
    "dim",
)

# A custom theme that predates the help roles inherits each missing one from
# the closest existing role instead of failing to load.
HELP_ROLE_FALLBACK = {
    "heading": "accent_bright",
    "prog": "accent_bright",
    "flag": "accent",
    "metavar": "progress",
    "choices": "success",
    "default": "muted",
    "dim": "muted",
}

ROLES = (
    "text",
    "accent",
    "accent_bright",
    "progress",
    "success",
    "warning",
    "error",
    "skip",
    "muted",
    "frame",
    *HELP_ROLES,
)
_BUILTIN_THEMES = frozenset(THEMES)

_mode = DEFAULT_COLOR_MODE
_theme = DEFAULT_THEME
_custom_themes = set()
_windows_ansi_ready = False


def theme_names():
    """Return the built-in theme names in display order."""
    return tuple(THEMES)


def is_builtin_theme(name: str) -> bool:
    return str(name).strip().lower() in _BUILTIN_THEMES


def normalize_palette(palette):
    """Complete a palette, filling help roles from their closest relatives.

    Core roles are required. A custom theme written before the help roles
    existed keeps working: each missing help role falls back to a related
    core role (for example ``heading`` to ``accent_bright``).
    """
    palette = {role: value for role, value in palette.items()}
    missing = [
        role for role in ROLES
        if role not in palette and role not in HELP_ROLES
    ]

    if missing:
        raise ValueError(
            f"Color theme is missing: {', '.join(missing)}"
        )

    for role in HELP_ROLES:
        if role not in palette:
            palette[role] = dict(palette[HELP_ROLE_FALLBACK[role]])

    return palette


def register_theme(name: str, palette) -> None:
    """Add a custom theme parsed from ``themes.ini``."""
    name = str(name).strip().lower()

    if not name:
        raise ValueError("A color theme needs a name")

    if name in THEMES and name not in _custom_themes:
        raise ValueError(
            f"Color theme '{name}' is built in; choose another name"
        )

    palette = normalize_palette(palette)

    for role in ROLES:
        entry = palette[role]

        if not isinstance(entry, dict) or set(entry) != {
            "16",
            "256",
            "truecolor",
        }:
            raise ValueError(
                f"Color theme '{name}' has an invalid value for '{role}'"
            )

    THEMES[name] = palette
    _custom_themes.add(name)


def set_theme(name: str) -> None:
    """Select one of the built-in or loaded custom color themes."""
    name = str(name).strip().lower()

    if name not in THEMES:
        raise ValueError(
            f"Unknown color theme '{name}' "
            f"(choose from {', '.join(THEMES)})"
        )

    global _theme
    _theme = name


def get_theme() -> str:
    return _theme


def set_color_mode(mode: str) -> None:
    """Choose how color is decided: ``auto``, ``always`` or ``never``."""
    if mode not in _COLOR_MODES:
        raise ValueError(
            f"Invalid color mode '{mode}' "
            f"(choose from {', '.join(_COLOR_MODES)})"
        )

    global _mode
    _mode = mode


def get_color_mode() -> str:
    return _mode


def _color_depth() -> str:
    """Pick the richest color format the terminal advertises."""
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "truecolor"

    if "256color" in os.environ.get("TERM", ""):
        return "256"

    return "16"


def _enable_windows_ansi() -> None:
    """Turn on virtual-terminal processing for classic Windows consoles."""
    global _windows_ansi_ready

    if os.name != "nt" or _windows_ansi_ready:
        return

    _windows_ansi_ready = True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()

        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)

    except (ImportError, AttributeError, OSError):
        # Enabling ANSI on a legacy console is best-effort: a missing
        # kernel32, a closed handle or an unsupported Windows version must
        # never break startup.
        pass


def color_enabled(stream=None) -> bool:
    """Return whether color should be written to ``stream`` (stdout)."""
    if _mode == "never":
        return False

    if _mode == "auto":
        if os.environ.get("NO_COLOR"):
            return False

        if os.environ.get("TERM") == "dumb":
            return False

        stream = sys.stdout if stream is None else stream

        try:
            if not stream.isatty():
                return False

        except (AttributeError, ValueError):
            return False

    _enable_windows_ansi()

    return True


def _role_code(role: str, depth: str):
    value = THEMES[_theme][role][depth]

    if value is None:
        return None

    if depth == "truecolor":
        return f"38;2;{value[0]};{value[1]};{value[2]}"

    if depth == "256":
        return f"38;5;{value}"

    return str(value)


def paint(text, *styles, stream=None) -> str:
    """Wrap ``text`` in theme roles and attributes, or leave it plain."""
    if not styles or not color_enabled(stream):
        return str(text)

    depth = _color_depth()
    codes = []

    for style in styles:
        # A name can be both a theme role and an attribute (only "dim" is).
        # The role wins when it has a color; otherwise the attribute applies,
        # which keeps Mono's colorless "dim" role visibly quieter.
        code = None

        if style in THEMES[_theme]:
            code = _role_code(style, depth)

        if code is None and style in _ATTRS:
            code = str(_ATTRS[style])

        if code is None and style not in THEMES[_theme]:
            raise ValueError(f"Unknown color style: {style!r}")

        if code and code not in codes:
            codes.append(code)

    if not codes:
        return str(text)

    return f"\x1b[{';'.join(codes)}m{text}{_RESET}"


def accent(value) -> str:
    return paint(value, "accent")


def accent_bright(value) -> str:
    return paint(value, "accent_bright")


def progress(value) -> str:
    return paint(value, "progress", "bold")


def success(value) -> str:
    return paint(value, "success", "bold")


def warning(value) -> str:
    return paint(value, "warning")


def error(value) -> str:
    return paint(value, "error", "bold")


def skip(value) -> str:
    return paint(value, "skip")


def muted(value) -> str:
    return paint(value, "muted")


def frame(value) -> str:
    return paint(value, "frame")


def heading(value) -> str:
    return paint(value, "accent_bright", "bold")


def label(value) -> str:
    return paint(value, "accent", "bold")


def bold(value) -> str:
    return paint(value, "bold")
