# SPDX-License-Identifier: GPL-3.0-or-later
"""Validation and parsing of source names, flags and intervals."""

import math

from ..config_pkg.constants import (
    ARTWORK_FALLBACKS,
    METADATA_PROVIDERS,
    MUSIC_PROVIDERS,
    PROVIDER_OPTIONS,
)
from ..enums import MusicSource


def split_source_names(value: str):
    return [
        item.strip().lower()
        for item in (value or "").split(",")
        if item.strip()
    ]


def normalize_metadata_sources(value: str):
    """Validate and de-duplicate a metadata provider list, preserving order."""
    names = []

    for name in split_source_names(value):
        if name in ARTWORK_FALLBACKS:
            raise ValueError(
                f"'{name}' is an artwork fallback, not a metadata provider"
            )

        if name not in METADATA_PROVIDERS:
            raise ValueError(
                f"Unknown metadata source '{name}' "
                f"(choose from {', '.join(METADATA_PROVIDERS)} or none)"
            )

        if name not in names:
            names.append(name)

    return names


def normalize_music_sources(value: str):
    """Validate and de-duplicate a music provider list, preserving order."""
    names = []

    for name in split_source_names(value):
        if name not in MUSIC_PROVIDERS:
            raise ValueError(
                f"Unknown music source '{name}' "
                f"(choose from {', '.join(MUSIC_PROVIDERS)})"
            )

        if name not in names:
            names.append(name)

    if not names:
        raise ValueError(
            "At least one music source is required "
            f"(choose from {', '.join(MUSIC_PROVIDERS)})"
        )

    return names


def normalize_disable_sources(value: str):
    names = []
    allowed = (
        METADATA_PROVIDERS
        + ARTWORK_FALLBACKS
        + (MusicSource.SOUNDCLOUD.value,)
    )

    for name in split_source_names(value):
        if name not in allowed:
            raise ValueError(
                f"Unknown source '{name}' "
                f"(choose from {', '.join(allowed)})"
            )

        if name not in names:
            names.append(name)

    return names


def parse_bool(value: str, label: str) -> bool:
    lowered = (value or "").strip().lower()

    if lowered in ("1", "true", "yes", "on"):
        return True

    if lowered in ("0", "false", "no", "off"):
        return False

    raise ValueError(
        f"Invalid boolean for '{label}': {value!r} "
        "(use true or false)"
    )


def parse_interval(value: str, label: str) -> float:
    try:
        interval = float(value)

    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid number for '{label}': {value!r}"
        ) from error

    if not math.isfinite(interval):
        raise ValueError(
            f"'{label}' must be a finite number: {value!r}"
        )

    if interval < 0:
        raise ValueError(f"'{label}' must not be negative: {value!r}")

    return interval


def parse_provider_options(values):
    """Parse --provider-opt NAME.KEY=VALUE arguments into typed settings."""
    options = []

    for raw in values or []:
        text = str(raw).strip()

        if "=" not in text:
            raise ValueError(
                f"Invalid --provider-opt '{raw}': expected NAME.KEY=VALUE"
            )

        target, value = text.split("=", 1)

        if "." not in target:
            raise ValueError(
                f"Invalid --provider-opt '{raw}': expected NAME.KEY=VALUE"
            )

        name, key = target.split(".", 1)
        name = name.strip().lower()
        key = key.strip().lower()
        value = value.strip()

        if name not in METADATA_PROVIDERS:
            raise ValueError(
                f"Unknown provider in --provider-opt: '{name}' "
                f"(choose from {', '.join(METADATA_PROVIDERS)})"
            )

        if key not in PROVIDER_OPTIONS[name]:
            allowed = ", ".join(sorted(PROVIDER_OPTIONS[name]))
            raise ValueError(
                f"Unknown option '{key}' for provider '{name}' "
                f"(choose from {allowed})"
            )

        if value == "":
            raise ValueError(
                f"Empty value in --provider-opt '{raw}'"
            )

        if key == "enabled":
            parsed = parse_bool(value, f"{name}.{key}")

        elif key == "min_interval":
            parsed = parse_interval(value, f"{name}.{key}")

        else:
            parsed = value.lower()

        options.append((name, key, parsed))

    return options


def threshold_value(value, default: float, label: str) -> float:
    if value is None:
        return default

    try:
        number = float(value)

    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid value for '{label}': {value!r}") from error

    if not math.isfinite(number):
        raise ValueError(
            f"'{label}' must be a finite number between 0.0 and 1.0: {value!r}"
        )

    if not 0.0 <= number <= 1.0:
        raise ValueError(
            f"'{label}' must be between 0.0 and 1.0: {value!r}"
        )

    return number
