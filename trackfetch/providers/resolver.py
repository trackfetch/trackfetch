# SPDX-License-Identifier: GPL-3.0-or-later
"""Provider selection, cooldowns and cache-aware metadata resolution."""

from ..config_pkg.config import SourceConfig, effective_metadata_sources
from ..core.matching import fallback_metadata, select_best_metadata
from ..core.runtime import MetadataRuntime
from ..errors import ProviderAuthError, ProviderError
from .registry import PROVIDER_FUNCTIONS

FALLBACK_METADATA_SOURCES = ("deezer", "musicbrainz")


def metadata_sources_for(config: SourceConfig, artist: str, title: str):
    """Configured providers plus safe free fallbacks.

    Fallbacks are only used after every configured provider missed, and never
    when the user disabled them or explicitly selected no metadata at all.
    """
    sources = effective_metadata_sources(config, artist, title)

    if config.none_selected:
        return sources

    for name in FALLBACK_METADATA_SOURCES:
        if name in sources or config.is_enabled(name):
            continue

        if config.providers[name].get("disabled"):
            continue

        sources.append(name)

    return sources


def cached_metadata(runtime, artist, title, provider, config):
    if runtime.cache is None:
        return None

    cached = runtime.cache.get(artist, title, provider)

    if cached is None:
        return None

    return select_best_metadata(
        [cached],
        artist,
        title,
        config.match_threshold,
        config.title_threshold,
    )


def _cached_or_none(runtime, artist, title, provider, config):
    """Return a cached match, or None when there is no usable cache entry."""
    return cached_metadata(runtime, artist, title, provider, config)


def _fetch_candidates(runtime, provider, artist, title, config):
    """Call one provider, recording auth, failure and malformed responses.

    Returns the candidate list, or None when the provider failed. The caller
    decides whether to fall back to a cache entry.
    """
    try:
        return PROVIDER_FUNCTIONS[provider](
            runtime,
            artist,
            title,
            config,
        )

    except ProviderAuthError:
        runtime.health.force_cooldown(provider, 600.0)
        return None

    except ProviderError:
        runtime.health.record_failure(provider)
        return None

    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        # A malformed but successful-looking API response is a failure,
        # not a reason to abort the whole run.
        runtime.health.record_failure(provider)
        return None


def resolve_metadata(artist: str, title: str, config: SourceConfig, runtime):
    """Return the first suitable metadata result in configured priority order.

    Free fallbacks are considered only after every configured provider missed.
    """
    if runtime is None:
        runtime = MetadataRuntime()

    fallback = fallback_metadata(artist, title)

    for provider in metadata_sources_for(config, artist, title):
        cooldown = runtime.health.in_cooldown(provider)

        if cooldown or runtime.health.state(provider)["failures"] == 0:
            cached = _cached_or_none(
                runtime, artist, title, provider, config
            )

            if cached is not None:
                return cached

            if cooldown:
                continue

        candidates = _fetch_candidates(
            runtime, provider, artist, title, config
        )

        if candidates is None:
            cached = _cached_or_none(
                runtime, artist, title, provider, config
            )

            if cached is not None:
                return cached

            continue

        best = select_best_metadata(
            candidates,
            artist,
            title,
            config.match_threshold,
            config.title_threshold,
        )

        # A valid response, even with no match, resets the failure counter.
        runtime.health.record_success(provider)

        if best is not None:
            if runtime.cache is not None:
                runtime.cache.set(artist, title, provider, best)

            return best

    return fallback
