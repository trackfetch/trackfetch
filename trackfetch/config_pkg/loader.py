# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve settings and CLI arguments into provider entries."""

import re
from dataclasses import dataclass

from ..config_pkg.constants import (
    ARTWORK_FALLBACKS,
    DEFAULT_METADATA_SOURCES,
    DEFAULT_MUSIC_SOURCES,
    METADATA_PROVIDERS,
    MUSIC_PROVIDERS,
    PROVIDER_DEFAULTS,
)
from .validate import (
    normalize_disable_sources,
    normalize_metadata_sources,
    normalize_music_sources,
    parse_bool,
    parse_interval,
    parse_provider_options,
)


@dataclass(frozen=True)
class ProviderFlags:
    """Enabled/disabled provider names from the config file and the CLI."""

    config_enabled: frozenset
    config_disabled: frozenset
    cli_enabled: frozenset
    cli_disabled: frozenset



def _provider_entries(settings):
    """Build provider entries from defaults plus config-file overrides."""
    providers = {}
    config_enabled = set()
    config_disabled = set()

    for name in METADATA_PROVIDERS:
        defaults = PROVIDER_DEFAULTS[name]
        entry = dict(defaults)
        entry["disabled"] = False

        enabled_key = f"{name}_enabled"
        interval_key = f"{name}_min_interval"

        if enabled_key in settings and str(settings[enabled_key]).strip():
            enabled = parse_bool(settings[enabled_key], enabled_key)
            entry["enabled"] = enabled

            if enabled:
                config_enabled.add(name)
            else:
                config_disabled.add(name)

        if interval_key in settings and str(settings[interval_key]).strip():
            entry["min_interval"] = parse_interval(
                settings[interval_key],
                interval_key,
            )

        if name == "itunes" and settings.get("itunes_country", "").strip():
            country = settings["itunes_country"].strip().lower()

            if not re.fullmatch(r"[a-z]{2}", country):
                raise ValueError(
                    f"Invalid value for 'itunes_country': "
                    f"{settings['itunes_country']!r} (use a two-letter code)"
                )

            entry["country"] = country

        providers[name] = entry

    return providers, config_enabled, config_disabled


def _apply_provider_options(providers, args):
    """Apply --provider key=value overrides; returns (cli_enabled, cli_disabled)."""
    cli_enabled = set()
    cli_disabled = set()

    for name, key, value in parse_provider_options(
        getattr(args, "provider_opt", None)
    ):
        if key == "enabled":
            providers[name]["enabled"] = value

            if value:
                cli_enabled.add(name)
                cli_disabled.discard(name)
            else:
                cli_disabled.add(name)
                cli_enabled.discard(name)

        elif key == "min_interval":
            providers[name]["min_interval"] = value

        elif key == "country":
            if not re.fullmatch(r"[a-z]{2}", value):
                raise ValueError(
                    f"Invalid value for '{name}.country': {value!r} "
                    "(use a two-letter code)"
                )

            providers[name]["country"] = value

    return cli_enabled, cli_disabled


def _resolve_metadata_sources(args, settings, providers, flags):
    """Resolve the metadata source list; returns (sources, none_selected)."""
    cli_raw = getattr(args, "metadata_sources", None)
    cli_sources_given = cli_raw is not None
    raw_sources = (
        cli_raw
        if cli_sources_given
        else config_str_value(settings, "metadata_sources")
    )

    none_selected = False

    if raw_sources is None:
        sources = list(DEFAULT_METADATA_SOURCES)

    elif (raw_sources or "").strip().lower() == "none":
        sources = []
        none_selected = True

    else:
        sources = normalize_metadata_sources(raw_sources)

    config_disabled_sources = set(
        normalize_disable_sources(
            config_str_value(settings, "disable_sources") or ""
        )
    )
    cli_disabled_sources = set(
        normalize_disable_sources(
            getattr(args, "disable_sources", None) or ""
        )
    )

    config_disables = set(flags.config_disabled) | (
        config_disabled_sources - set(ARTWORK_FALLBACKS)
    )
    cli_disables = set(flags.cli_disabled) | (
        cli_disabled_sources - set(ARTWORK_FALLBACKS)
    )

    if cli_sources_given:
        # A CLI selection is an explicit override of the configured source
        # list and of any configured disabling of those providers. Only an
        # explicit CLI disable may remove a selected provider.
        remove = set(cli_disables)
        # A config disable still blocks VocaDB promotion unless the provider
        # was also explicitly selected or enabled on the CLI.
        disabled_for_promotion = set(cli_disables) | (
            config_disables - set(sources) - set(flags.cli_enabled)
        )
    else:
        # An explicit CLI provider enable still wins over config disabling,
        # but never over an explicit CLI disable.
        remove = (config_disables - set(flags.cli_enabled)) | set(cli_disables)
        disabled_for_promotion = set(remove)

    sources = [name for name in sources if name not in remove]

    if not none_selected:
        append_enabled = set(flags.cli_enabled)

        if not cli_sources_given:
            append_enabled.update(flags.config_enabled)

        for name in METADATA_PROVIDERS:
            if name in append_enabled and name not in sources and name not in remove:
                sources.append(name)

    for name in METADATA_PROVIDERS:
        providers[name]["enabled"] = name in sources
        providers[name]["disabled"] = name in disabled_for_promotion

    return sources, none_selected


def _music_flags(args, settings, config_disabled_sources,
                 cli_disabled_sources):
    """Collect config/CLI music enable and disable sets."""
    config_enabled = set()
    config_disabled = set()

    for name in MUSIC_PROVIDERS:
        key = f"{name}_enabled"

        if key in settings and str(settings[key]).strip():
            enabled = parse_bool(settings[key], key)

            if enabled:
                config_enabled.add(name)
            else:
                config_disabled.add(name)

    config_disabled |= config_disabled_sources & set(MUSIC_PROVIDERS)

    cli_enabled = set()
    cli_disabled = set()

    for name in MUSIC_PROVIDERS:
        value = getattr(args, f"{name}_enabled", None)

        if value is not None:
            if value:
                cli_enabled.add(name)
            else:
                cli_disabled.add(name)

    cli_disabled |= cli_disabled_sources & set(MUSIC_PROVIDERS)
    return config_enabled, config_disabled, cli_enabled, cli_disabled


def _resolve_music_sources(args, settings, config_disabled_sources,
                           cli_disabled_sources):
    """Resolve the music source priority list."""
    # Music providers follow the same precedence as metadata providers:
    # CLI list > config list > defaults, with explicit disables always winning
    # and explicit enables appending to the configured priority.
    (
        config_music_enabled,
        config_music_disabled,
        cli_music_enabled,
        cli_music_disabled,
    ) = _music_flags(args, settings, config_disabled_sources,
                     cli_disabled_sources)

    cli_music_raw = getattr(args, "music_sources", None)
    cli_music_given = cli_music_raw is not None
    raw_music = (
        cli_music_raw
        if cli_music_given
        else config_str_value(settings, "music_sources")
    )

    if raw_music is None:
        music_sources = list(DEFAULT_MUSIC_SOURCES)
    else:
        music_sources = normalize_music_sources(raw_music)

    if cli_music_given:
        # An explicit CLI priority list overrides configured disabling and
        # `*_enabled=false` for the providers it names.
        remove = set(cli_music_disabled)
    else:
        remove = (config_music_disabled - cli_music_enabled) | set(
            cli_music_disabled
        )

    music_sources = [name for name in music_sources if name not in remove]

    append_enabled = set(cli_music_enabled)

    # An explicit priority list is authoritative: a stale `*_enabled = true`
    # in the config file must not add a provider back to it. The flags still
    # append on the command line, because they are an explicit request.
    if raw_music is None:
        append_enabled |= config_music_enabled

    for name in MUSIC_PROVIDERS:
        if (
            name in append_enabled
            and name not in music_sources
            and name not in remove
        ):
            music_sources.append(name)

    if not music_sources:
        raise ValueError(
            "At least one music source must stay enabled "
            f"(choose from {', '.join(MUSIC_PROVIDERS)})"
        )

    return music_sources


def config_str_value(settings, key):
    """Read a plain string setting, or None when it is missing or blank."""
    value = (settings.get(key) or "").strip()

    if not value:
        return None

    return value
