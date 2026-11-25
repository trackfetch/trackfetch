# SPDX-License-Identifier: GPL-3.0-or-later
"""The per-song download pipeline."""

import shutil
import tempfile
from pathlib import Path

import mutagen
import requests

from .. import colors, soundcloud, youtube
from ..config import build_source_config
from ..config_pkg.constants import (
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_FORMAT,
    LYRICS_DEFAULT_ENABLED,
    SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    SOUNDCLOUD_DEFAULT_TRIGGER,
)
from ..context import RunContext
from ..enums import MusicSource
from ..errors import CoverError, ProviderError, YoutubeSearchError
from ..files import make_filename
from ..images import download_best_cover
from ..lyrics import fetch_lyrics, write_lrc_sidecar
from ..providers.resolver import resolve_metadata
from ..reporter import Reporter
from ..result import Result
from ..tags import add_metadata
from ..youtube import (
    download_audio,
    find_youtube_video,
    is_age_restriction_error,
    is_bot_check_error,
    probe_age_restriction,
    youtube_thumbnail_urls,
)

_report = Reporter()


def _lyrics_lines(metadata, ctx: RunContext):
    """Fetch lyrics and print their status. Returns the lyrics dict or None."""
    lyrics_enabled = (
        LYRICS_DEFAULT_ENABLED
        if ctx.source_config is None
        else ctx.source_config.lyrics_enabled
    )

    if not lyrics_enabled:
        return None

    lyrics = None
    lyrics_error = False

    try:
        lyrics = fetch_lyrics(
            metadata["artist"],
            metadata["title"],
            ctx.runtime,
            duration=metadata.get("duration"),
        )

    except (
        requests.RequestException,
        ProviderError,
        ValueError,
        OSError,
    ) as error:
        lyrics_error = True
        _report.label_plain("Lyrics:", f"not found ({error})")

    if lyrics:
        timed = bool(lyrics.get("synced"))

        if timed:
            place = (
                "sidecar + tags"
                if ctx.lyrics_type == "sidecar"
                else "embedded"
            )
            _report.label_success("Lyrics:", f"synced ({place})")

        else:
            _report.label_plain("Lyrics:", "plain only (no synced version)")

    elif not lyrics_error:
        _report.label_plain("Lyrics:", "not found")

    return lyrics


def _download_and_tag(metadata, video, video_url, ctx: RunContext,
                      youtube_enabled):
    """Download one chosen result, tag it and move it into place.

    Returns a :class:`Result`. ``download_failed`` is True only when yt-dlp
    itself returned no audio, so the caller can decide whether the result is
    an age restriction worth a fallback.
    """
    filename = make_filename(
        metadata,
        ctx.title_only,
        ctx.audio_format,
    )

    final_path = ctx.output / filename

    if final_path.exists():
        _report.skip(f"already exists: {filename}")
        return Result(True, "exists")

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        audio_path = download_audio(
            video_url,
            temp_dir,
            ctx.audio_format,
            ctx.audio_quality,
        )

        if not audio_path:
            return Result(False, "yt-dlp download failed", True)

        cover_path = download_best_cover(
            metadata,
            temp_dir / "cover",
            fallback_urls=(
                youtube_thumbnail_urls(video) if youtube_enabled else []
            ),
        )

        if cover_path is None:
            cover_path = temp_dir / "cover.jpg"

        lyrics = _lyrics_lines(metadata, ctx)

        try:
            add_metadata(
                audio_path,
                cover_path,
                metadata,
                lyrics,
                ctx.lyrics_type,
            )

        except (
            mutagen.MutagenError,
            CoverError,
            KeyError,
            ValueError,
            OSError,
        ) as error:
            return Result(False, f"metadata error: {error}")

        try:
            shutil.move(
                str(audio_path),
                str(final_path),
            )

            try:
                write_lrc_sidecar(final_path, lyrics, ctx.lyrics_type)

            except OSError as error:
                _report.warning(f"WARNING: could not write LRC file: {error}")

        except OSError as error:
            return Result(False, f"move error: {error}")

    _report.success(f"SUCCESS: {filename}")

    return Result(True, "downloaded")


def _soundcloud_artwork(candidate):
    """Return the largest SoundCloud artwork URL, or None."""
    thumbnails = candidate.get("thumbnails")

    if isinstance(thumbnails, list):
        ordered = sorted(
            (
                item
                for item in thumbnails
                if isinstance(item, dict) and item.get("url")
            ),
            key=lambda item: (
                (item.get("width") or 0) * (item.get("height") or 0),
                (item.get("width") or 0) + (item.get("height") or 0),
            ),
            reverse=True,
        )

        if ordered:
            return ordered[0]["url"]

    thumbnail = candidate.get("thumbnail")

    if isinstance(thumbnail, str) and thumbnail:
        return thumbnail

    return None


def _soundcloud_fallback(metadata, ctx: RunContext, age_restricted=None,
                         fallback_names=None, primary=False):
    """Search SoundCloud and download at most once.

    Nothing is downloaded until a single candidate is either confident or
    explicitly chosen by the user. Returns ``(ok, reason)``.
    """
    if primary:
        _report.muted(
            "Searching SoundCloud as the primary music source."
        )

    elif age_restricted is True:
        _report.warning(
            "AGE-RESTRICTED: YouTube requires sign-in for this video."
        )

    else:
        _report.muted(
            "YouTube had no usable result; looking for the track "
            "on SoundCloud."
        )

    source_config = ctx.source_config

    result = soundcloud.find_soundcloud_fallback(
        metadata["artist"],
        metadata["title"],
        metadata.get("duration"),
        enabled=source_config.soundcloud_enabled,
        min_score=source_config.soundcloud_min_score,
        min_margin=source_config.soundcloud_min_margin,
        ambiguous=getattr(
            source_config,
            "soundcloud_ambiguous",
            SOUNDCLOUD_DEFAULT_AMBIGUOUS,
        ),
        fallback_names=fallback_names,
    )

    if not result.selected or not result.candidate:
        return False, soundcloud.describe_failure(result)

    # The search results were already enriched with --dump-single-json
    # metadata, so the selected candidate is verified without another call.
    candidate = result.candidate

    blocked = soundcloud.blocked_reason(candidate)

    if blocked:
        _report.fail_raw(f"FAILED: SoundCloud track {blocked}")
        return False, f"SoundCloud {blocked}"

    preview = soundcloud.preview_reason(
        candidate,
        metadata.get("duration"),
    )

    if preview:
        _report.fail_raw(f"FAILED: SoundCloud track is {preview}")
        return False, f"SoundCloud {preview}"

    webpage_url = candidate.get("webpage_url")

    if not webpage_url:
        _report.fail("Invalid SoundCloud result")
        return False, "invalid SoundCloud result"

    _report.label(
        "Selected:",
        f"{candidate.get('title', 'Unknown')} "
        f"{colors.muted('(SoundCloud)')}",
    )

    # Keep the provider artwork; only add SoundCloud art when the metadata
    # source had none, so the tags stay consistent with the rest of the run.
    tagged_metadata = metadata

    if not metadata.get("cover_url"):
        artwork = _soundcloud_artwork(candidate)

        if artwork:
            tagged_metadata = dict(metadata)
            tagged_metadata["cover_url"] = artwork

    download = _download_and_tag(
        tagged_metadata,
        {
            "title": candidate.get("title"),
            "thumbnails": candidate.get("thumbnails"),
            "thumbnail": candidate.get("thumbnail"),
        },
        webpage_url,
        ctx,
        # SoundCloud artwork replaces the YouTube thumbnail fallback.
        False,
    )

    return download.ok, download.reason


def _fallback_allowed(reason, source_config, age_restricted=None, blocked=None):
    """Decide whether the SoundCloud fallback may run for this failure.

    The trigger is configurable:

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
    if source_config is None or not source_config.soundcloud_enabled:
        return False

    trigger = getattr(
        source_config,
        "soundcloud_trigger",
        SOUNDCLOUD_DEFAULT_TRIGGER,
    )

    login_wall = age_restricted is True or blocked is True
    missing = reason in ("no confident YouTube match", "no YouTube result")

    if trigger == "age":
        return age_restricted is True

    if trigger == "blocked":
        return login_wall

    if trigger == "age-or-missing":
        return login_wall or missing

    return trigger == "any"


def _maybe_soundcloud_fallback(reason, metadata, ctx: RunContext,
                               age_restricted=None, blocked=None,
                               fallback_names=None):
    """Run the SoundCloud fallback when the trigger allows it.

    Returns the normal ``(ok, reason)`` pair, falling back to the original
    failure reason when SoundCloud is not allowed or finds nothing.
    """
    if not _fallback_allowed(
        reason,
        ctx.source_config,
        age_restricted,
        blocked,
    ):
        return False, reason

    return _soundcloud_fallback(
        metadata,
        ctx,
        age_restricted=age_restricted,
        fallback_names=fallback_names,
    )


def _youtube_attempt(metadata, ctx: RunContext, youtube_enabled,
                     fallback_names=None, allow_soundcloud_fallback=True):
    """Search YouTube, download one result and optionally fall back.

    Returns the usual ``(ok, reason)`` pair. When SoundCloud is the primary
    source and YouTube is only the fallback, the caller passes
    ``allow_soundcloud_fallback=False`` so a failure does not loop back to
    SoundCloud.
    """
    youtube.LAST_SEARCH_HAD_CANDIDATES = False

    try:
        video = find_youtube_video(
            metadata["artist"],
            metadata["title"],
            metadata.get("duration"),
        )

    except YoutubeSearchError as error:
        _report.fail(f"yt-dlp search failed: {error}")
        return False, "yt-dlp search failed"

    if not video:
        if youtube.LAST_SEARCH_HAD_CANDIDATES:
            reason = "no confident YouTube match"
            _report.fail("No confident YouTube match")

        else:
            reason = "no YouTube result"
            _report.fail("No YouTube result")

        if not allow_soundcloud_fallback:
            return False, reason

        return _maybe_soundcloud_fallback(
            reason,
            metadata,
            ctx,
            fallback_names=fallback_names,
        )

    video_url = (
        video.get("webpage_url")
        or video.get("url")
    )

    if not video_url:
        video_id = video.get("id")

        if video_id:
            video_url = (
                "https://www.youtube.com/watch?v="
                + video_id
            )

    if not video_url:
        _report.fail("Invalid YouTube result")
        return False, "invalid YouTube result"

    download = _download_and_tag(metadata, video, video_url, ctx,
                                 youtube_enabled)

    if download.ok or not download.download_failed:
        return download.ok, download.reason

    if not allow_soundcloud_fallback:
        return False, download.reason

    # The download's own stderr is the most reliable signal: a bot check
    # often lets --dump-single-json through and only fails here. Fall back
    # to the metadata probe for yt-dlp versions that stay quiet.
    download_error = youtube.LAST_DOWNLOAD_ERROR
    age_restricted = is_age_restriction_error(download_error)
    blocked = is_bot_check_error(download_error)

    if not age_restricted and not blocked:
        age_restricted = probe_age_restriction(video_url)

    return _maybe_soundcloud_fallback(
        download.reason,
        metadata,
        ctx,
        age_restricted=age_restricted,
        blocked=blocked,
        fallback_names=fallback_names,
    )


def process_song(
    input_artist,
    input_title,
    output,
    title_only,
    audio_format=DEFAULT_FORMAT,
    audio_quality=DEFAULT_AUDIO_QUALITY,
    source_config=None,
    runtime=None,
    lyrics_type=None,
):
    if source_config is None:
        source_config = build_source_config(None, {})

    metadata = resolve_metadata(
        input_artist,
        input_title,
        source_config,
        runtime,
    )
    youtube_enabled = source_config.youtube_enabled

    if lyrics_type is None:
        lyrics_type = source_config.lyrics_type

    ctx = RunContext(
        output=output,
        title_only=title_only,
        audio_format=audio_format,
        audio_quality=audio_quality,
        source_config=source_config,
        runtime=runtime,
        lyrics_type=lyrics_type,
    )

    _report.label(
        "Metadata:",
        f"{metadata['artist']} - "
        f"{metadata['title']}",
    )

    filename = make_filename(
        metadata,
        ctx.title_only,
        ctx.audio_format,
    )

    if (ctx.output / filename).exists():
        _report.skip(f"already exists: {filename}")
        return True, "exists"

    music_sources = list(source_config.music_sources)

    if not music_sources:
        _report.fail("No music sources enabled")
        return False, "no music sources enabled"

    if music_sources[0] == MusicSource.SOUNDCLOUD.value:
        ok, reason = _soundcloud_fallback(
            metadata,
            ctx,
            fallback_names=(input_artist, input_title),
            primary=True,
        )

        if ok:
            return ok, reason

        if MusicSource.YOUTUBE.value not in music_sources:
            return ok, reason

        _report.muted(
            "SoundCloud did not produce a track; trying YouTube."
        )

        return _youtube_attempt(
            metadata,
            ctx,
            youtube_enabled,
            fallback_names=(input_artist, input_title),
            allow_soundcloud_fallback=False,
        )

    if not youtube_enabled:
        _report.fail("YouTube is disabled")
        return False, "YouTube disabled"

    return _youtube_attempt(
        metadata,
        ctx,
        youtube_enabled,
        fallback_names=(input_artist, input_title),
        allow_soundcloud_fallback=(
            MusicSource.SOUNDCLOUD.value in music_sources
        ),
    )
