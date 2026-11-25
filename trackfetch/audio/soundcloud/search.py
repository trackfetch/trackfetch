# SPDX-License-Identifier: GPL-3.0-or-later
"""SoundCloud queries through yt-dlp: search, details and result parsing.

No audio is downloaded here. The functions only ask yt-dlp for the flat
search listing or for the full metadata of one track.
"""

import json
import subprocess
import unicodedata

from ...config_pkg.constants import (
    SOUNDCLOUD_DETAILS_TIMEOUT,
    SOUNDCLOUD_SEARCH_LIMIT,
    SOUNDCLOUD_SEARCH_TIMEOUT,
)
from ...errors import SoundcloudError


def _duration(value):
    """Return a positive duration in seconds, or None when it is unusable."""
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (TypeError, ValueError):
        return None

    if number <= 0:
        return None

    return number


def _run_ytdlp(command, timeout):
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    except subprocess.TimeoutExpired:
        raise SoundcloudError(
            f"yt-dlp timed out after {timeout}s"
        ) from None

    except OSError as error:
        raise SoundcloudError(f"could not run yt-dlp: {error}") from error


def _error_text(result):
    return (getattr(result, "stderr", "") or "").strip()


def soundcloud_search(query: str, limit: int = SOUNDCLOUD_SEARCH_LIMIT):
    """Return the raw yt-dlp ``scsearch`` results for a query."""
    query = " ".join((query or "").split())

    if not query:
        return []

    command = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        f"scsearch{limit}:{query}",
    ]
    result = _run_ytdlp(command, SOUNDCLOUD_SEARCH_TIMEOUT)

    if getattr(result, "returncode", 0) != 0:
        raise SoundcloudError(
            f"yt-dlp SoundCloud search failed (exit {result.returncode})"
            + (f": {_error_text(result)}" if _error_text(result) else "")
        )

    entries = []

    for line in (result.stdout or "").splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            data = json.loads(line)

        except ValueError:
            continue

        if isinstance(data, dict):
            entries.append(data)

    return entries


def soundcloud_track_details(url: str):
    """Fetch full metadata for one SoundCloud track without downloading it."""
    if not url:
        raise SoundcloudError("SoundCloud track has no URL")

    command = [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--dump-single-json",
        url,
    ]
    result = _run_ytdlp(command, SOUNDCLOUD_DETAILS_TIMEOUT)

    if getattr(result, "returncode", 0) != 0:
        raise SoundcloudError(
            f"yt-dlp SoundCloud metadata failed (exit {result.returncode})"
            + (f": {_error_text(result)}" if _error_text(result) else "")
        )

    try:
        data = json.loads(result.stdout or "")

    except ValueError:
        raise SoundcloudError(
            "yt-dlp returned invalid SoundCloud metadata"
        ) from None

    if not isinstance(data, dict):
        raise SoundcloudError("yt-dlp returned invalid SoundCloud metadata")

    return data


def parse_search_result(data):
    """Translate one yt-dlp SoundCloud entry into a compact candidate.

    Returns None when the entry has no usable identity. Missing optional
    fields are kept as None so that scoring can decide how much they matter.
    """
    if not isinstance(data, dict):
        return None

    title = (data.get("track") or data.get("title") or "").strip()
    webpage_url = (data.get("webpage_url") or "").strip()
    track_id = str(data.get("id") or "").strip()

    if not title or not (webpage_url or track_id):
        return None

    artists = data.get("artists")

    if isinstance(artists, list):
        artists = [
            str(name).strip()
            for name in artists
            if isinstance(name, str) and name.strip()
        ]

    else:
        artists = []

    artist = (data.get("artist") or "").strip() or None

    return {
        "id": track_id or None,
        "title": title,
        "raw_title": (data.get("title") or title).strip(),
        "artist": artist,
        "artists": artists,
        "uploader": (data.get("uploader") or "").strip() or None,
        "duration": _duration(data.get("duration")),
        "webpage_url": webpage_url or None,
        "license": (data.get("license") or "").strip() or None,
        "thumbnails": data.get("thumbnails"),
        "thumbnail": data.get("thumbnail"),
        "streamable": data.get("streamable"),
        "downloadable": data.get("downloadable"),
        "policy": data.get("policy"),
        "is_preview": bool(data.get("is_preview") or data.get("preview")),
        "playlist_index": data.get("playlist_index"),
    }


def is_formats_preview(details):
    """Whether yt-dlp's format list looks like a short SoundCloud preview."""
    formats = (details or {}).get("formats")

    if not isinstance(formats, list):
        return False

    return any(
        str((item or {}).get("format_id") or "").lower().startswith("preview")
        for item in formats
        if isinstance(item, dict)
    )


def merge_details(candidate, details):
    """Overlay a details payload on a search candidate without losing fields."""
    if not isinstance(details, dict):
        return dict(candidate)

    merged = dict(candidate)

    for key in (
        "id",
        "artist",
        "duration",
        "license",
        "thumbnails",
        "thumbnail",
        "streamable",
        "downloadable",
        "policy",
        "webpage_url",
    ):
        if details.get(key) is not None:
            merged[key] = details[key]

    for key in ("title", "track"):
        if details.get(key):
            merged[key] = str(details[key]).strip()

    if isinstance(details.get("artists"), list):
        merged["artists"] = [
            str(name).strip()
            for name in details["artists"]
            if isinstance(name, str) and name.strip()
        ]

    if details.get("is_preview") or details.get("preview"):
        merged["is_preview"] = True

    if is_formats_preview(details):
        merged["is_preview"] = True

    merged["duration"] = _duration(merged.get("duration"))

    return merged


def normalize_title_text(value):
    """NFC-normalize an upload title before comparisons."""
    return unicodedata.normalize("NFC", value or "").strip()


__all__ = [
    "is_formats_preview",
    "merge_details",
    "normalize_title_text",
    "parse_search_result",
    "soundcloud_search",
    "soundcloud_track_details",
]
