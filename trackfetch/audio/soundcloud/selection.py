# SPDX-License-Identifier: GPL-3.0-or-later
"""Candidate selection, ambiguity handling and trigger rules.

These functions decide whether a ranked SoundCloud candidate may be taken
without asking, and when a fallback is allowed at all. They never search or
download.
"""

import sys

from ...config_pkg.constants import SOUNDCLOUD_MIN_MARGIN, SOUNDCLOUD_MIN_SCORE
from ...ui import colors
from .search import _duration

STATUS_SELECTED = "selected"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_LOW_CONFIDENCE = "low-confidence"
STATUS_NO_MATCH = "no-match"
STATUS_ERROR = "error"
STATUS_DISABLED = "disabled"


class FallbackResult:
    """Outcome of a SoundCloud fallback attempt."""

    def __init__(self, status, candidate=None, candidates=None, error=None):
        self.status = status
        self.candidate = candidate
        self.candidates = list(candidates or [])
        self.error = error

    @property
    def selected(self):
        return self.status == STATUS_SELECTED

    def __repr__(self):
        return (
            f"FallbackResult(status={self.status!r}, "
            f"candidate={self.candidate!r})"
        )


def trigger_allows(trigger, reason, age_restricted=None, blocked=None):
    """Decide whether the SoundCloud fallback may run for this failure.

    ``age``
        only an age restriction (the safe default);
    ``blocked``
        an age restriction or a YouTube login/bot wall, which also needs
        credentials we deliberately do not use;
    ``age-or-missing``
        ``blocked`` plus a YouTube search that found no confident match;
    ``any``
        every failed search or download.

    Network errors, private/unavailable videos and invalid URLs stay outside
    every state except ``any``, so their handling is unchanged.
    """
    login_wall = age_restricted is True or blocked is True
    missing = reason in ("no confident YouTube match", "no YouTube result")

    if trigger == "age":
        return age_restricted is True

    if trigger == "blocked":
        return login_wall

    if trigger == "age-or-missing":
        return login_wall or missing

    return trigger == "any"


def select_candidate(
    ranked,
    min_score=SOUNDCLOUD_MIN_SCORE,
    min_margin=SOUNDCLOUD_MIN_MARGIN,
):
    """Pick one candidate, or explain why the user has to choose.

    Returns ``(candidate, reason)``. ``candidate`` is None for every status
    other than "selected".
    """
    approved = [
        item for item in ranked or []
        if not item.get("reject_reason")
    ]

    if not approved:
        return None, STATUS_NO_MATCH

    best = approved[0]

    if best.get("score", 0.0) < min_score:
        return None, STATUS_LOW_CONFIDENCE

    if (
        len(approved) > 1
        and best.get("score", 0.0) - approved[1].get("score", 0.0)
        < min_margin
    ):
        return None, STATUS_AMBIGUOUS

    return best, STATUS_SELECTED


def format_duration(seconds):
    duration = _duration(seconds)

    if duration is None:
        return "?:??"

    total = int(round(duration))
    return f"{total // 60}:{total % 60:02d}"


def format_candidate(candidate, number=None):
    prefix = f"{number}. " if number is not None else ""
    uploader = candidate.get("uploader") or candidate.get("artist") or "unknown"
    duration = format_duration(candidate.get("duration"))

    return (
        f"{prefix}{candidate.get('title', 'Unknown')} "
        f"{colors.muted(f'({duration}, {uploader})')}"
    )


def print_options(candidates):
    print(
        colors.warning(
            "Multiple SoundCloud results are plausible:"
        )
    )

    for number, candidate in enumerate(candidates, start=1):
        line = format_candidate(candidate, number)
        url = candidate.get("webpage_url")

        if url:
            line += f" {colors.muted(url)}"

        print(f"  {line}")

        if candidate.get("duration_score") is not None:
            print(
                colors.muted(
                    f"     match {candidate.get('score', 0):.2f} "
                    f"(title {candidate.get('title_score', 0):.2f}, "
                    f"artist {candidate.get('artist_score', 0):.2f}, "
                    f"duration {candidate.get('duration_score', 0):.2f})"
                )
            )


def prompt_for_candidate(
    candidates,
    input_func=input,
    stream=None,
):
    """Let the user pick a candidate, or skip when there is no terminal.

    Non-interactive runs (cron, redirected stdin, test harnesses) never
    download blindly: the options are printed and None is returned.
    """
    if not candidates:
        return None

    print_options(candidates)
    stream = sys.stdin if stream is None else stream

    try:
        interactive = bool(stream.isatty())

    except (AttributeError, ValueError):
        interactive = False

    if not interactive:
        print(
            colors.muted(
                "SoundCloud skipped: choose a result interactively "
                "to download one."
            )
        )
        return None

    try:
        answer = input_func(
            "Choose a SoundCloud result "
            f"[1-{len(candidates)}, Enter to skip]: "
        )

    except (EOFError, KeyboardInterrupt):
        print()
        return None

    answer = (answer or "").strip()

    if not answer:
        return None

    try:
        index = int(answer)

    except ValueError:
        print(colors.muted("Not a number; skipping SoundCloud."))
        return None

    if not 1 <= index <= len(candidates):
        print(colors.muted("Out of range; skipping SoundCloud."))
        return None

    return candidates[index - 1]


def _report_scores(ranked):
    for item in ranked:
        reason = item.get("reject_reason")
        suffix = f" [{reason}]" if reason else ""
        print(
            colors.muted(
                f"  SoundCloud score {item.get('score', 0):.2f}: "
                f"{item.get('title', 'Unknown')}{suffix}"
            )
        )


def _take_best(approved, ranked):
    chosen = dict(approved[0])
    chosen.pop("reject_reason", None)
    return FallbackResult(
        STATUS_SELECTED,
        candidate=chosen,
        candidates=ranked,
    )


def _status_result(ranked, opts):
    """Turn a ranked list into a FallbackResult before any user choice."""
    approved = [item for item in ranked if not item.get("reject_reason")]
    candidate, status = select_candidate(
        ranked,
        min_score=opts.min_score,
        min_margin=opts.min_margin,
    )

    _report_scores(ranked)

    if status == STATUS_NO_MATCH:
        print(colors.muted("No suitable SoundCloud match."))
        return FallbackResult(STATUS_NO_MATCH, candidates=ranked), approved

    if status == STATUS_LOW_CONFIDENCE:
        best = approved[0]
        print(
            colors.muted(
                "Best SoundCloud match is below the confidence threshold "
                f"({best.get('score', 0):.2f} < {opts.min_score:.2f})."
            )
        )

        if opts.ambiguous == "best":
            print(
                colors.warning(
                    "Taking the highest scoring SoundCloud result anyway "
                    f"({best.get('score', 0):.2f}, "
                    f"{best.get('title', 'Unknown')}) because "
                    "soundcloud_ambiguous is 'best'. "
                    "Check the file if it matters."
                )
            )
            return _take_best(approved, ranked), approved

        return FallbackResult(STATUS_LOW_CONFIDENCE, candidates=approved), approved

    if status == STATUS_AMBIGUOUS:
        print(colors.muted("Several SoundCloud results are close."))

        if opts.ambiguous == "best" and approved:
            # soundcloud_ambiguous=best asks for the top result instead of a
            # question, which keeps unattended runs moving. It is a setting,
            # not a detected lack of terminal, so do not claim otherwise.
            print(
                colors.muted(
                    "Taking the highest scoring SoundCloud result "
                    "(soundcloud_ambiguous=best)."
                )
            )
            return _take_best(approved, ranked), approved

        return FallbackResult(STATUS_AMBIGUOUS, candidates=approved), approved

    return FallbackResult(
        STATUS_SELECTED,
        candidate=candidate,
        candidates=ranked,
    ), approved


def _choose_candidate(result, approved, opts):
    """Ask the chooser when no result is selected yet."""
    if result.selected or not approved:
        return result

    chooser = prompt_for_candidate if opts.chooser is None else opts.chooser

    try:
        choice = chooser(approved)

    except (EOFError, KeyboardInterrupt):
        print()
        choice = None

    if not isinstance(choice, dict):
        return result

    chosen = dict(choice)
    chosen.pop("reject_reason", None)
    return FallbackResult(
        STATUS_SELECTED,
        candidate=chosen,
        candidates=result.candidates,
    )

def describe_failure(result):
    """A short, user-facing reason for a failed fallback."""
    if result is None:
        return "SoundCloud fallback failed"

    return {
        STATUS_NO_MATCH: "no SoundCloud match",
        STATUS_LOW_CONFIDENCE: "no confident SoundCloud match",
        STATUS_AMBIGUOUS: "ambiguous SoundCloud matches",
        STATUS_ERROR: "SoundCloud search failed",
        STATUS_DISABLED: "SoundCloud fallback unavailable",
    }.get(result.status, "SoundCloud fallback failed")


__all__ = [
    "FallbackResult",
    "STATUS_AMBIGUOUS",
    "STATUS_DISABLED",
    "STATUS_ERROR",
    "STATUS_LOW_CONFIDENCE",
    "STATUS_NO_MATCH",
    "STATUS_SELECTED",
    "describe_failure",
    "format_candidate",
    "format_duration",
    "print_options",
    "prompt_for_candidate",
    "select_candidate",
    "trigger_allows",
]
