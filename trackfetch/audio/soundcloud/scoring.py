# SPDX-License-Identifier: GPL-3.0-or-later
"""SoundCloud candidate scoring and version/preview checks.

The weights live in :class:`trackfetch.scoring.SoundcloudScoring`; the
functions here only apply them to a candidate dictionary.
"""

from ...config_pkg.constants import (
    SOUNDCLOUD_DURATION_TOLERANCE,
    SOUNDCLOUD_PREVIEW_RATIO,
    SOUNDCLOUD_PREVIEW_SECONDS,
)
from ...scoring import DEFAULT_SOUNDCLOUD_SCORING
from .search import _duration
from .title import (
    _candidate_artist_names,
    _contains_artist,
    _cross_script_similarity,
    _title_score,
    is_version_mismatch,
)

# Words that mark a different version of a song. A result containing one of
# them is only accepted when the requested title contains it as well.
VERSION_MARKERS = (
    "remix",
    "rmx",
    "bootleg",
    "mashup",
    "cover",
    "karaoke",
    "instrumental",
    "nightcore",
    "sped up",
    "slowed",
    "reverb",
    "live",
    "concert",
    "acoustic",
    "piano version",
    "8d audio",
)

# Metadata fields that explicitly forbid a normal stream/download. An
# accessible stream alone is not treated as permission, but an explicit
# block from SoundCloud is always honored.
BLOCKED_POLICIES = ("BLOCK", "SNIP", "PREVIEW")


def _artist_score(candidate, artist, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    names = _candidate_artist_names(candidate)

    if not names:
        return 0.0

    score = max(
        _cross_script_similarity(artist, name)
        for name in names
    )

    for name in names:
        # The uploader handle ("nuclear_gandhi") is weak evidence; only an
        # explicit artist field or a title prefix gets the containment boost.
        if name == candidate.get("uploader"):
            continue

        if _contains_artist(artist, name):
            score = max(score, scoring.contains_artist_score)

    return min(score, 1.0)


def preview_reason(candidate, expected_duration):
    """Return why a candidate looks like a preview, or None.

    The 30-second SoundCloud preview of a 2:41 track is the motivating case.
    Duration metadata can be missing, so an absent value is never a reason to
    reject on its own.
    """
    duration = _duration(candidate.get("duration"))

    if candidate.get("is_preview"):
        return "marked as a preview"

    if duration is None:
        return None

    if duration <= 15:
        return "too short to be the full track"

    expected = _duration(expected_duration)

    if expected is not None:
        if expected >= 60 and duration < expected * SOUNDCLOUD_PREVIEW_RATIO:
            return "shorter than the expected track"

        if expected >= 30 and duration > expected * 3:
            return "much longer than the expected track"

    elif duration < SOUNDCLOUD_PREVIEW_SECONDS:
        return "short upload without a known duration to compare"

    return None


def _blocked_reason(candidate):
    if candidate.get("streamable") is False:
        return "not streamable"

    if candidate.get("downloadable") is False:
        return "downloads disabled by the uploader"

    policy = str(candidate.get("policy") or "").upper()

    if policy in BLOCKED_POLICIES:
        return f"blocked by SoundCloud ({policy.lower()})"

    return None


def blocked_reason(candidate):
    """Public wrapper: why SoundCloud will not provide this track, or None."""
    return _blocked_reason(candidate or {})


def duration_score(candidate, expected_duration, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Score duration similarity, or None when either side is unknown."""
    duration = _duration(candidate.get("duration"))
    expected = _duration(expected_duration)

    if duration is None or expected is None:
        return None

    difference = abs(duration - expected)

    if difference <= scoring.duration_exact_limit:
        return scoring.duration_exact_score

    if difference <= SOUNDCLOUD_DURATION_TOLERANCE:
        return scoring.duration_near_score

    ratio = difference / max(duration, expected)

    if ratio <= scoring.duration_close_ratio_limit:
        return scoring.duration_close_score

    if ratio <= scoring.duration_far_ratio_limit:
        return scoring.duration_far_score

    return 0.0


def _extra_score(candidate, artist, title, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Small bonus for explicit artist evidence and clean metadata."""
    evidence = 0.0

    explicit = [candidate.get("artist"), *(candidate.get("artists") or [])]
    explicit = [name for name in explicit if name]

    if explicit and (
        _artist_score({"artists": explicit}, artist, scoring)
        >= scoring.explicit_artist_min_score
    ):
        evidence = 1.0

    elif _contains_artist(artist, candidate.get("uploader") or ""):
        evidence = scoring.uploader_evidence_score

    elif _contains_artist(artist, candidate.get("raw_title") or ""):
        evidence = scoring.raw_title_evidence_score

    # A titled upload with no artist information anywhere is weaker.
    if not any(_candidate_artist_names(candidate)):
        evidence = 0.0

    return evidence


def _reject_reason(candidate, title, title_value, duration,
                   scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Return the first explicit rejection reason, or None."""
    reason = None

    if not (candidate.get("title") or "").strip():
        reason = "no title metadata"

    elif title_value < scoring.min_title_score:
        reason = "title does not match"

    elif is_version_mismatch(candidate, title):
        reason = "remix, cover or another version"

    if reason is None:
        reason = preview_reason(candidate, duration)

    if reason is None:
        reason = _blocked_reason(candidate)

    if reason is None and candidate.get("is_live"):
        reason = "live stream"

    return reason


def score_candidate(candidate, artist, title, duration=None, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Score one candidate and attach rejection details.

    The weights follow the task brief: title 40%, artist 30%, duration 20%,
    additional metadata 10%. Duration is neutral when either side lacks it;
    previews and version mismatches are rejected explicitly instead of only
    losing points.
    """
    scored = dict(candidate)
    title_value = _title_score(candidate, title, artist, scoring)
    artist_value = _artist_score(candidate, artist, scoring)
    duration_value = duration_score(candidate, duration, scoring)
    extra_value = _extra_score(candidate, artist, title, scoring)

    effective_duration = (
        scoring.neutral_duration_score
        if duration_value is None
        else duration_value
    )

    total = (
        title_value * scoring.title_weight
        + artist_value * scoring.artist_weight
        + effective_duration * scoring.duration_weight
        + extra_value * scoring.extra_weight
    )

    reason = _reject_reason(candidate, title, title_value, duration, scoring)

    scored.update(
        {
            "score": round(total, 4),
            "title_score": round(title_value, 4),
            "artist_score": round(artist_value, 4),
            "duration_score": (
                None if duration_value is None else round(duration_value, 4)
            ),
            "extra_score": round(extra_value, 4),
            "reject_reason": reason,
        }
    )

    return scored


def rank_candidates(candidates, artist, title, duration=None, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Score and rank parsed candidates, best first."""
    scored = [
        score_candidate(candidate, artist, title, duration, scoring)
        for candidate in candidates or []
        if isinstance(candidate, dict)
    ]
    scored.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return scored


__all__ = [
    "blocked_reason",
    "duration_score",
    "preview_reason",
    "rank_candidates",
    "score_candidate",
]
