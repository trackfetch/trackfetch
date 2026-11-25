# SPDX-License-Identifier: GPL-3.0-or-later
"""YouTube search orchestration, audio downloading and public names.

The low-level pieces live in focused submodules; this module keeps the
historical mutable state (``LAST_SEARCH_HAD_CANDIDATES`` and
``LAST_DOWNLOAD_ERROR``) and the two orchestration entry points.
"""

from pathlib import Path

from ... import colors
from ...config_pkg.constants import (
    AUDIO_FORMATS,
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_TITLE_THRESHOLD,
    YOUTUBE_MIN_SCORE,
    YOUTUBE_MUSIC_DETAIL_CANDIDATES,
    YOUTUBE_MUSIC_MAX_DURATION_DIFF,
    YTDLP_REMOTE_COMPONENTS,
)
from ...enums import AudioFormat
from ...errors import YoutubeSearchError
from ...matching import MIN_ARTIST_SIMILARITY
from .age_probe import (
    is_age_restriction_error,
    is_bot_check_error,
    probe_age_restriction,
)
from .download import run_streaming as _run_streaming
from .scoring import (
    _contains_artist,
    cross_script_similarity,
    details_artist_similarity,
    duration_difference,
    has_artist_evidence,
    score_youtube_result,
    search_queries,
)
from .search import (
    youtube_music_search,
    youtube_search,
    youtube_thumbnail_urls,
    youtube_video_details,
)

# Set by find_youtube_video() so callers can tell "nothing was found at all"
# apart from "results existed, but none was confident enough".
LAST_SEARCH_HAD_CANDIDATES = False

# Tail of the last real download's stderr, so the pipeline can classify the
# failure. The metadata probe is not enough: a bot check often still lets
# --dump-single-json through and only fails at download time.
LAST_DOWNLOAD_ERROR = ""


def _music_fallback(artist: str, title: str, duration=None):
    """Try YouTube Music when the three plain searches found nothing usable.

    YouTube filters anonymous ytsearch results for some topics. The Music
    search endpoint is not filtered, but its flat results carry no artist or
    duration, so each plausible title is verified with a details call before
    it can be used.
    """
    global LAST_SEARCH_HAD_CANDIDATES

    query = " ".join(f"{artist} {title}".split())
    print(colors.muted(f"Searching YouTube Music: {query}"))

    flat = youtube_music_search(query)

    if not flat:
        return None

    LAST_SEARCH_HAD_CANDIDATES = True
    ranked = []

    for video in flat:
        title_score = cross_script_similarity(
            title,
            video.get("title", ""),
        )

        if title_score >= DEFAULT_TITLE_THRESHOLD:
            ranked.append((title_score, video.get("id")))

    ranked.sort(key=lambda item: item[0], reverse=True)

    best_video = None
    best_score = -999.0

    for _, video_id in ranked[:YOUTUBE_MUSIC_DETAIL_CANDIDATES]:
        try:
            details = youtube_video_details(video_id)

        # A single failing details call must not lose the other candidates.
        except YoutubeSearchError:
            continue

        if details_artist_similarity(artist, details) < MIN_ARTIST_SIMILARITY:
            continue

        difference = duration_difference(
            details.get("duration"),
            duration,
        )

        if (
            difference is not None
            and difference > YOUTUBE_MUSIC_MAX_DURATION_DIFF
        ):
            continue

        score = score_youtube_result(details, artist, title, duration)
        print(
            colors.muted(
                f"  YouTube score {score:.2f}: "
                f"{details.get('title', 'Unknown')}"
            )
        )

        if score > best_score:
            best_score = score
            best_video = details

    if best_video:
        print(
            f"{colors.label('Selected:')} "
            f"{best_video.get('title', 'Unknown')}"
        )

    return best_video


def find_youtube_video(artist: str, title: str, duration=None):
    global LAST_SEARCH_HAD_CANDIDATES

    LAST_SEARCH_HAD_CANDIDATES = False
    seen = set()
    scored = []

    for index, query in enumerate(search_queries(artist, title)):
        print(colors.muted(f"Searching YouTube: {query}"))

        videos = youtube_search(query, limit=5)
        added = False

        for video in videos or []:
            key = video.get("id") or (
                video.get("title"),
                video.get("channel") or video.get("uploader"),
            )

            if key in seen:
                continue

            seen.add(key)
            added = True

            score = score_youtube_result(
                video,
                artist,
                title,
                duration,
            )
            scored.append((score, video, index == 0))

            print(
                colors.muted(
                    f"  YouTube score {score:.2f}: "
                    f"{video.get('title', 'Unknown')}"
                )
            )

        if not videos or not added:
            continue

        LAST_SEARCH_HAD_CANDIDATES = True
        best_video = None
        best_score = -999.0

        for score, video, artist_query in scored:
            if score < YOUTUBE_MIN_SCORE:
                continue

            if not artist_query and not has_artist_evidence(
                video,
                artist,
                title,
                duration,
            ):
                continue

            if score > best_score:
                best_score = score
                best_video = video

        if best_video:
            print(
                f"{colors.label('Selected:')} "
                f"{best_video.get('title', 'Unknown')}"
            )

            return best_video

    return _music_fallback(artist, title, duration)


def download_audio(
    video_url: str,
    temp_dir: Path,
    audio_format: AudioFormat | str = AudioFormat.MP3,
    audio_quality: int = DEFAULT_AUDIO_QUALITY,
):
    """Download and convert audio, recording yt-dlp's error on failure."""
    global LAST_DOWNLOAD_ERROR

    audio_format = AudioFormat(audio_format)
    format_value = audio_format.value
    template = str(temp_dir / "audio.%(ext)s")

    command = [
        "yt-dlp",
        *AUDIO_FORMATS[audio_format],
        "-x",
        "--audio-format",
        format_value,
        "--audio-quality",
        str(audio_quality),
        "--remote-components",
        YTDLP_REMOTE_COMPONENTS,
        "--no-playlist",
        "-o",
        template,
        video_url,
    ]

    LAST_DOWNLOAD_ERROR = ""

    try:
        returncode, error_text = _run_streaming(command)

    except OSError as error:
        LAST_DOWNLOAD_ERROR = str(error)
        return None

    LAST_DOWNLOAD_ERROR = error_text

    if returncode != 0:
        return None

    files = list(temp_dir.glob(f"audio.{format_value}"))

    if not files:
        return None

    return files[0]


__all__ = [
    "LAST_DOWNLOAD_ERROR",
    "LAST_SEARCH_HAD_CANDIDATES",
    "YoutubeSearchError",
    "_contains_artist",
    "download_audio",
    "find_youtube_video",
    "is_age_restriction_error",
    "is_bot_check_error",
    "probe_age_restriction",
    "score_youtube_result",
    "youtube_music_search",
    "youtube_search",
    "youtube_thumbnail_urls",
    "youtube_video_details",
]
