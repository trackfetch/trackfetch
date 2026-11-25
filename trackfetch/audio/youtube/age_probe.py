# SPDX-License-Identifier: GPL-3.0-or-later
"""Age-restriction and login-wall detection for yt-dlp errors."""

import subprocess

# yt-dlp phrases that specifically mean "age restriction". Anything else,
# such as "Video unavailable", "Private video" or a network error, must keep
# the existing failure handling and must not trigger a fallback.
AGE_RESTRICTION_PATTERNS = (
    "sign in to confirm your age",
    "confirm your age",
    "age-restricted",
    "age restricted",
    "age_verification_required",
    "age_check_required",
    "inappropriate for some users",
    "age-gate",
    "age gate",
    "age verification required",
    "requires age verification",
)


# yt-dlp phrases that mean YouTube is gating the download behind a login.
# This is not an age restriction: it is a bot/account check that can hit any
# video. Both mean "YouTube will not give us the file without credentials",
# which is exactly when looking for another copy is reasonable.
BOT_CHECK_PATTERNS = (
    "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot",
    "confirm you're not a bot",
    "confirm you’re not a bot",
    "sign in to confirm your age",
    "confirm your age",
    "use --cookies-from-browser",
    "use --cookies for the authentication",
    "this video requires payment",
    "members-only content",
)


def is_bot_check_error(text) -> bool:
    """Whether a yt-dlp error is a login/bot wall rather than a real refusal."""
    if not text:
        return False

    lowered = str(text).lower()
    return any(pattern in lowered for pattern in BOT_CHECK_PATTERNS)


def is_age_restriction_error(text) -> bool:
    """Whether a yt-dlp error message is an age-restriction error.

    Only the specific age-gate phrases count. Login prompts for other
    reasons ("confirm you're not a bot"), unavailable/private videos and
    network failures return False.
    """
    if not text:
        return False

    lowered = str(text).lower()
    return any(pattern in lowered for pattern in AGE_RESTRICTION_PATTERNS)


def probe_age_restriction(video_url, timeout=60):
    """Return whether fetching this video fails *specifically* on age.

    A metadata-only yt-dlp call reproduces the same gate as the download.
    It never attempts authentication, cookies or alternate clients: the
    answer is simply "is this error an age restriction". Malformed output,
    timeouts, network errors and every other failure return False so the
    existing handling stays in charge.
    """
    if not video_url:
        return False

    command = [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--dump-single-json",
        video_url,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    except (subprocess.TimeoutExpired, OSError):
        return False

    if getattr(result, "returncode", 0) == 0:
        return False

    return is_age_restriction_error(
        getattr(result, "stderr", "") or ""
    )


__all__ = [
    "AGE_RESTRICTION_PATTERNS",
    "BOT_CHECK_PATTERNS",
    "is_age_restriction_error",
    "is_bot_check_error",
    "probe_age_restriction",
]
