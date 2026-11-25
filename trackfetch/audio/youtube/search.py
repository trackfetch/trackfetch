# SPDX-License-Identifier: GPL-3.0-or-later
"""YouTube queries through yt-dlp: search, details and thumbnails."""

import json
import re
import subprocess
from urllib.parse import quote_plus

from ...config_pkg.constants import (
    YOUTUBE_MUSIC_SEARCH_LIMIT,
    YTDLP_REMOTE_COMPONENTS,
)
from ...errors import YoutubeSearchError

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_thumbnail_urls(video):
    """Return thumbnail URLs for a YouTube result, best first."""
    urls = []
    thumbnails = (video or {}).get("thumbnails")

    if isinstance(thumbnails, list):
        ordered = sorted(
            (
                item for item in thumbnails
                if isinstance(item, dict) and item.get("url")
            ),
            key=lambda item: (
                (item.get("width") or 0) * (item.get("height") or 0)
            ),
            reverse=True,
        )

        urls.extend(item["url"] for item in ordered)

    thumbnail = (video or {}).get("thumbnail")

    if isinstance(thumbnail, str) and thumbnail:
        urls.append(thumbnail)

    video_id = (video or {}).get("id")

    if video_id:
        urls.append(
            f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        )
        urls.append(
            f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        )

    result = []

    for url in urls:
        if url not in result:
            result.append(url)

    return result


def _search_error(result):
    """Build the exception for a failed yt-dlp run, keeping its stderr."""
    returncode = getattr(result, "returncode", 0)
    stderr = (getattr(result, "stderr", "") or "").strip()
    error = YoutubeSearchError(
        f"yt-dlp search failed (exit {returncode})"
        + (f": {stderr}" if stderr else "")
    )
    error.stderr = stderr
    return error


def _run_ytdlp(command):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _json_lines(output):
    videos = []

    for line in output.splitlines():
        try:
            data = json.loads(line)
            videos.append(data)
        except json.JSONDecodeError:
            pass

    return videos


def youtube_search(query: str, limit: int = 5):
    command = [
        "yt-dlp",
        "--remote-components",
        YTDLP_REMOTE_COMPONENTS,
        "--flat-playlist",
        "--dump-json",
        f"ytsearch{limit}:{query}",
    ]

    result = _run_ytdlp(command)

    if getattr(result, "returncode", 0) != 0:
        raise _search_error(result)

    return _json_lines(result.stdout)


def youtube_music_search(
    query: str,
    limit: int = YOUTUBE_MUSIC_SEARCH_LIMIT,
):
    """Search YouTube Music, which is not filtered like anonymous ytsearch.

    The Music search endpoint returns entries for playlists, channels and
    albums too, so only 11-character video ids are kept. The flat result has
    no artist or duration; callers must verify candidates with
    youtube_video_details().
    """
    url = (
        "https://music.youtube.com/search?q="
        + quote_plus(query)
        + "#songs"
    )
    command = [
        "yt-dlp",
        "--remote-components",
        YTDLP_REMOTE_COMPONENTS,
        "--flat-playlist",
        "-I",
        f"1:{limit}",
        "--dump-json",
        url,
    ]

    result = _run_ytdlp(command)

    if getattr(result, "returncode", 0) != 0:
        raise _search_error(result)

    return [
        data
        for data in _json_lines(result.stdout)
        if isinstance(data, dict)
        and VIDEO_ID_RE.match(str(data.get("id") or ""))
    ]


def youtube_video_details(video_id):
    """Fetch full metadata for one video id."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    command = [
        "yt-dlp",
        "--remote-components",
        YTDLP_REMOTE_COMPONENTS,
        "--skip-download",
        "--no-playlist",
        "--dump-single-json",
        url,
    ]

    result = _run_ytdlp(command)

    if getattr(result, "returncode", 0) != 0:
        raise _search_error(result)

    try:
        return json.loads(result.stdout)

    except json.JSONDecodeError:
        raise YoutubeSearchError(
            f"yt-dlp returned invalid details for {video_id}"
        ) from None


__all__ = [
    "VIDEO_ID_RE",
    "youtube_music_search",
    "youtube_search",
    "youtube_thumbnail_urls",
    "youtube_video_details",
]
