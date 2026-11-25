# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a SourceConfig from CLI flags, config settings and defaults."""

from ..config_pkg.constants import (
    CACHE_DEFAULT_ENABLED,
    DEFAULT_LYRICS_TYPE,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_TITLE_THRESHOLD,
    LYRICS_DEFAULT_ENABLED,
    LYRICS_TYPES,
    SOUNDCLOUD_AMBIGUOUS_MODES,
    SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    SOUNDCLOUD_DEFAULT_TRIGGER,
    SOUNDCLOUD_MIN_MARGIN,
    SOUNDCLOUD_MIN_SCORE,
    SOUNDCLOUD_TRIGGERS,
)
from .loader import (
    ProviderFlags,
    _apply_provider_options,
    _provider_entries,
    _resolve_metadata_sources,
    _resolve_music_sources,
    config_str_value,
    normalize_disable_sources,
    parse_bool,
)
from .model import LyricsOptions, SoundcloudPolicy, SourceConfig, Thresholds
from .validate import threshold_value


def _resolve_feature_flags(args, settings):
    """Resolve lyrics/cache toggles and the lyrics type."""
    lyrics_enabled = LYRICS_DEFAULT_ENABLED

    if "lyrics_enabled" in settings and str(settings["lyrics_enabled"]).strip():
        lyrics_enabled = parse_bool(
            settings["lyrics_enabled"],
            "lyrics_enabled",
        )

    cli_lyrics = getattr(args, "lyrics_enabled", None)

    if cli_lyrics is not None:
        lyrics_enabled = bool(cli_lyrics)

    cache_enabled = CACHE_DEFAULT_ENABLED

    if "cache_enabled" in settings and str(settings["cache_enabled"]).strip():
        cache_enabled = parse_bool(
            settings["cache_enabled"],
            "cache_enabled",
        )

    cli_cache = getattr(args, "cache_enabled", None)

    if cli_cache is not None:
        cache_enabled = bool(cli_cache)

    lyrics_type = DEFAULT_LYRICS_TYPE
    config_lyrics_type = config_str_value(settings, "lyrics_type")

    if config_lyrics_type is not None:
        config_lyrics_type = config_lyrics_type.strip().lower()

        if config_lyrics_type not in LYRICS_TYPES:
            raise ValueError(
                f"Unknown value for 'lyrics_type': {config_lyrics_type!r} "
                f"(choose from {', '.join(LYRICS_TYPES)})"
            )

        lyrics_type = config_lyrics_type

    cli_lyrics_type = getattr(args, "lyrics_type", None)

    if cli_lyrics_type is not None:
        if cli_lyrics_type not in LYRICS_TYPES:
            raise ValueError(
                f"Unknown value for 'lyrics_type': {cli_lyrics_type!r} "
                f"(choose from {', '.join(LYRICS_TYPES)})"
            )

        lyrics_type = cli_lyrics_type

    return lyrics_enabled, cache_enabled, lyrics_type


def _resolve_soundcloud_options(args, settings):
    """Resolve SoundCloud thresholds, trigger and ambiguity mode."""
    soundcloud_min_score = threshold_value(
        getattr(args, "soundcloud_min_score", None),
        threshold_value(
            settings.get("soundcloud_min_score"),
            SOUNDCLOUD_MIN_SCORE,
            "soundcloud_min_score",
        ),
        "soundcloud_min_score",
    )
    soundcloud_min_margin = threshold_value(
        getattr(args, "soundcloud_min_margin", None),
        threshold_value(
            settings.get("soundcloud_min_margin"),
            SOUNDCLOUD_MIN_MARGIN,
            "soundcloud_min_margin",
        ),
        "soundcloud_min_margin",
    )

    soundcloud_trigger = SOUNDCLOUD_DEFAULT_TRIGGER
    config_trigger = config_str_value(settings, "soundcloud_trigger")

    if config_trigger is not None:
        config_trigger = config_trigger.strip().lower()

        if config_trigger not in SOUNDCLOUD_TRIGGERS:
            raise ValueError(
                f"Unknown value for 'soundcloud_trigger': {config_trigger!r} "
                f"(choose from {', '.join(SOUNDCLOUD_TRIGGERS)})"
            )

        soundcloud_trigger = config_trigger

    cli_trigger = getattr(args, "soundcloud_trigger", None)

    if cli_trigger is not None:
        if cli_trigger not in SOUNDCLOUD_TRIGGERS:
            raise ValueError(
                f"Unknown value for 'soundcloud_trigger': {cli_trigger!r} "
                f"(choose from {', '.join(SOUNDCLOUD_TRIGGERS)})"
            )

        soundcloud_trigger = cli_trigger

    soundcloud_ambiguous = SOUNDCLOUD_DEFAULT_AMBIGUOUS
    config_ambiguous = config_str_value(settings, "soundcloud_ambiguous")

    if config_ambiguous is not None:
        config_ambiguous = config_ambiguous.strip().lower()

        if config_ambiguous not in SOUNDCLOUD_AMBIGUOUS_MODES:
            raise ValueError(
                f"Unknown value for 'soundcloud_ambiguous': "
                f"{config_ambiguous!r} "
                f"(choose from {', '.join(SOUNDCLOUD_AMBIGUOUS_MODES)})"
            )

        soundcloud_ambiguous = config_ambiguous

    cli_ambiguous = getattr(args, "soundcloud_ambiguous", None)

    if cli_ambiguous is not None:
        if cli_ambiguous not in SOUNDCLOUD_AMBIGUOUS_MODES:
            raise ValueError(
                f"Unknown value for 'soundcloud_ambiguous': {cli_ambiguous!r} "
                f"(choose from {', '.join(SOUNDCLOUD_AMBIGUOUS_MODES)})"
            )

        soundcloud_ambiguous = cli_ambiguous

    return soundcloud_min_score, soundcloud_min_margin, soundcloud_trigger, \
        soundcloud_ambiguous


def _resolve_thresholds(args, settings):
    """Resolve the two score thresholds from CLI, config and defaults."""
    match_threshold = threshold_value(
        getattr(args, "match_threshold", None),
        threshold_value(
            settings.get("match_threshold"),
            DEFAULT_MATCH_THRESHOLD,
            "match_threshold",
        ),
        "match_threshold",
    )
    title_threshold = threshold_value(
        getattr(args, "title_threshold", None),
        threshold_value(
            settings.get("title_threshold"),
            DEFAULT_TITLE_THRESHOLD,
            "title_threshold",
        ),
        "title_threshold",
    )
    return match_threshold, title_threshold


def build_source_config(args, settings):
    """Resolve CLI flags, config settings and built-in defaults.

    Precedence is CLI > config.ini > built-in defaults. The result does not
    permanently change any user configuration.
    """
    settings = settings or {}

    providers, config_enabled, config_disabled = _provider_entries(settings)
    cli_enabled, cli_disabled = _apply_provider_options(providers, args)
    flags = ProviderFlags(
        frozenset(config_enabled),
        frozenset(config_disabled),
        frozenset(cli_enabled),
        frozenset(cli_disabled),
    )

    sources, none_selected = _resolve_metadata_sources(
        args,
        settings,
        providers,
        flags,
    )

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

    music_sources = _resolve_music_sources(
        args,
        settings,
        config_disabled_sources,
        cli_disabled_sources,
    )
    lyrics_enabled, cache_enabled, lyrics_type = _resolve_feature_flags(
        args,
        settings,
    )
    (
        soundcloud_min_score,
        soundcloud_min_margin,
        soundcloud_trigger,
        soundcloud_ambiguous,
    ) = _resolve_soundcloud_options(args, settings)

    match_threshold, title_threshold = _resolve_thresholds(args, settings)

    return SourceConfig(
        metadata_sources=sources,
        music_sources=music_sources,
        providers=providers,
        thresholds=Thresholds(
            match=match_threshold,
            title=title_threshold,
        ),
        soundcloud=SoundcloudPolicy(
            min_score=soundcloud_min_score,
            min_margin=soundcloud_min_margin,
            trigger=soundcloud_trigger,
            ambiguous=soundcloud_ambiguous,
        ),
        lyrics=LyricsOptions(
            enabled=lyrics_enabled,
            type=lyrics_type,
            cache=cache_enabled,
        ),
        none_selected=none_selected,
    )
