# SPDX-License-Identifier: GPL-3.0-or-later
"""SoundCloud fallback for YouTube videos blocked by an age restriction.

This is a search for an independently available copy of a track on another
platform. It never tries to bypass YouTube's age verification: no cookies, no
credentials and no alternate YouTube clients are used here.

The package is deliberately independent from the CLI and from the pipeline so
that the matching rules can be tested with plain dictionaries instead of live
network calls. The public names are re-exported here so the historical
``trackfetch.soundcloud`` module keeps working.
"""

from dataclasses import dataclass

from ...config_pkg.constants import (
    SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    SOUNDCLOUD_DEFAULT_ENABLED,
    SOUNDCLOUD_DETAILS_LIMIT,
    SOUNDCLOUD_MIN_MARGIN,
    SOUNDCLOUD_MIN_SCORE,
    SOUNDCLOUD_SEARCH_LIMIT,
)
from ...core.matching import normalize
from ...errors import SoundcloudError
from ...ui import colors
from .download import download_soundcloud_audio
from .scoring import (
    blocked_reason,
    duration_score,
    preview_reason,
    rank_candidates,
    score_candidate,
)
from .search import (
    is_formats_preview,
    merge_details,
    parse_search_result,
    soundcloud_search,
    soundcloud_track_details,
)
from .selection import (
    STATUS_AMBIGUOUS,
    STATUS_DISABLED,
    STATUS_ERROR,
    STATUS_LOW_CONFIDENCE,
    STATUS_NO_MATCH,
    STATUS_SELECTED,
    FallbackResult,
    _choose_candidate,
    _status_result,
    describe_failure,
    format_candidate,
    format_duration,
    prompt_for_candidate,
    select_candidate,
    trigger_allows,
)
from .title import is_version_mismatch

# The same track can appear more than once during one run (for example when
# the user retries an entry). Only the first attempt is allowed to search.
_ATTEMPTED = set()


@dataclass(frozen=True)
class FallbackOptions:
    """Grouped parameters for one SoundCloud fallback attempt."""

    enabled: bool = SOUNDCLOUD_DEFAULT_ENABLED
    min_score: float = SOUNDCLOUD_MIN_SCORE
    min_margin: float = SOUNDCLOUD_MIN_MARGIN
    ambiguous: str = SOUNDCLOUD_DEFAULT_AMBIGUOUS
    limit: int = SOUNDCLOUD_SEARCH_LIMIT
    chooser: object = None
    attempt_key: str = None
    details_limit: int = SOUNDCLOUD_DETAILS_LIMIT
    details_func: object = None
    fallback_names: object = None


def reset_attempts():
    """Forget which fallbacks were already tried (used by tests)."""
    _ATTEMPTED.clear()


reset_soundcloud_attempts = reset_attempts


def fetch_candidate_details(
    candidates,
    limit=SOUNDCLOUD_DETAILS_LIMIT,
    details_func=None,
):
    """Overlay ``--dump-single-json`` metadata on the first few candidates.

    The flat search result already carries title, duration and uploader, but
    the details call adds the license, explicit block flags and the exact
    duration. A failed call keeps the search payload, so one unavailable
    track never hides the others. No audio is downloaded here.
    """
    if details_func is None:
        details_func = soundcloud_track_details

    enriched = []

    for index, candidate in enumerate(candidates or []):
        if index >= limit or not isinstance(candidate, dict):
            enriched.append(candidate)
            continue

        url = candidate.get("webpage_url")

        if not url:
            enriched.append(candidate)
            continue

        try:
            enriched.append(merge_details(candidate, details_func(url)))

        except SoundcloudError as error:
            print(
                colors.muted(
                    "  SoundCloud metadata unavailable, using search data: "
                    f"{error}"
                )
            )
            enriched.append(candidate)

    return enriched


def _rank_with_details(candidates, artist, title, duration, opts, details_func):
    """Enrich candidates with metadata and rank them, or return []."""
    if not candidates:
        return []

    enriched = fetch_candidate_details(
        candidates,
        limit=opts.details_limit,
        details_func=details_func,
    )
    return rank_candidates(enriched, artist, title, duration)


def _search_and_rank(artist, title, duration, opts, search_func, details_func):
    """Run one search, parse its entries and rank them.

    Returns ``(ranked, error)``; ``error`` is None for an empty successful
    search and the message for a failed yt-dlp call.
    """
    query = " ".join(f"{artist} {title}".split())
    print(colors.muted(f"Searching SoundCloud: {query}"))

    try:
        entries = search_func(query, limit=opts.limit)

    except SoundcloudError as error:
        print(colors.warning(f"WARNING: SoundCloud search failed: {error}"))
        return [], str(error)

    candidates = [
        candidate
        for candidate in (parse_search_result(entry) for entry in entries)
        if candidate is not None
    ]

    if not candidates:
        print(colors.muted("No SoundCloud results."))

    return _rank_with_details(
        candidates,
        artist,
        title,
        duration,
        opts,
        details_func,
    ), None


def _retry_with_input_names(ranked, artist, title, opts, search_func, details_func):
    """Retry with the names from the input file when metadata names missed.

    The metadata artist can be a different act. Only when the first pass has
    no usable result are the original names tried as well.
    """
    if not opts.fallback_names or any(
        not item.get("reject_reason") for item in ranked
    ):
        return ranked

    other_artist, other_title = opts.fallback_names

    if (
        normalize(other_artist) == normalize(artist)
        and normalize(other_title) == normalize(title)
    ):
        return ranked

    print(
        colors.muted(
            "Retrying SoundCloud with the original input names: "
            f"{' '.join(f'{other_artist} {other_title}'.split())}"
        )
    )

    other_ranked, _error = _search_and_rank(
        other_artist,
        other_title,
        # The duration came from the mismatched metadata record, so it
        # describes a different recording. Keep it out of scoring rather
        # than penalizing a correct full-length upload for not matching
        # the wrong track's length.
        None,
        opts,
        search_func,
        details_func,
    )

    if other_ranked:
        return other_ranked

    return ranked


def _run_fallback(artist, title, duration, opts):
    if not opts.enabled:
        return FallbackResult(STATUS_DISABLED)

    key = opts.attempt_key or f"{normalize(artist)}|{normalize(title)}"

    if key in _ATTEMPTED:
        print(colors.muted("SoundCloud fallback already attempted; skipping."))
        return FallbackResult(STATUS_DISABLED, error="already attempted")

    _ATTEMPTED.add(key)
    details_func = opts.details_func or soundcloud_track_details

    ranked, error = _search_and_rank(
        artist,
        title,
        duration,
        opts,
        soundcloud_search,
        details_func,
    )

    if error is not None:
        return FallbackResult(STATUS_ERROR, error=error)

    ranked = _retry_with_input_names(
        ranked,
        artist,
        title,
        opts,
        soundcloud_search,
        details_func,
    )
    result, approved = _status_result(ranked, opts)
    return _choose_candidate(result, approved, opts)


def find_soundcloud_fallback(
    artist,
    title,
    duration=None,
    options=None,
):
    """Search SoundCloud and return the best candidate or user options.

    ``options`` groups the fallback parameters in :class:`FallbackOptions`;
    every field has the same default as before.

    The flat search results are enriched with ``--dump-single-json`` metadata
    (up to ``details_limit`` tracks) before scoring. The function never
    downloads audio: the caller downloads only the candidate returned as
    selected.
    """
    opts = options or FallbackOptions()
    return _run_fallback(artist, title, duration, opts)


__all__ = [
    "FallbackOptions",
    "FallbackResult",
    "STATUS_AMBIGUOUS",
    "STATUS_DISABLED",
    "STATUS_ERROR",
    "STATUS_LOW_CONFIDENCE",
    "STATUS_NO_MATCH",
    "STATUS_SELECTED",
    "blocked_reason",
    "describe_failure",
    "download_soundcloud_audio",
    "duration_score",
    "fetch_candidate_details",
    "find_soundcloud_fallback",
    "format_candidate",
    "format_duration",
    "is_formats_preview",
    "is_version_mismatch",
    "merge_details",
    "parse_search_result",
    "preview_reason",
    "prompt_for_candidate",
    "rank_candidates",
    "reset_attempts",
    "reset_soundcloud_attempts",
    "score_candidate",
    "select_candidate",
    "soundcloud_search",
    "soundcloud_track_details",
    "trigger_allows",
]
