# SPDX-License-Identifier: GPL-3.0-or-later
"""The per-song download pipeline."""

import shutil
import tempfile
from pathlib import Path

import mutagen
import requests

from .. import soundcloud, youtube
from ..config import build_source_config
from ..config_pkg.constants import (
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_FORMAT,
    LYRICS_DEFAULT_ENABLED,
)
from ..context import RunContext
from ..enums import MusicSource
from ..errors import CoverError, ProviderError
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
    probe_age_restriction,
    youtube_thumbnail_urls,
)
from .sources import (
    SourceOutcome,
    SourceSelection,
    _soundcloud_artwork,
    build_registry,
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


def _download_and_tag(selection: SourceSelection, ctx: RunContext, download):
    """Download one chosen result, tag it and move it into place.

    Returns a :class:`Result`. ``download_failed`` is True only when yt-dlp
    itself returned no audio, so the caller can decide whether the result is
    an age restriction worth a fallback.
    """
    metadata = selection.metadata
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

        audio_path = download(
            selection.url,
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
                youtube_thumbnail_urls(selection.video)
                if selection.allow_thumbnails
                else []
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


def _source_registry(ctx, fallback_names):
    """Build the source registry, injecting the patchable pipeline globals."""
    return build_registry(
        ctx,
        youtube_module=youtube,
        soundcloud_module=soundcloud,
        find_youtube=find_youtube_video,
        download_audio=download_audio,
        probe_age_restriction=probe_age_restriction,
        fallback_names=fallback_names,
    )


def _try_music_sources(metadata, ctx: RunContext, fallback_names):
    """Walk the configured music sources until one produces a file."""
    music_sources = [MusicSource(name) for name in ctx.source_config.music_sources]

    if not music_sources:
        _report.fail("No music sources enabled")
        return False, "no music sources enabled"

    registry = _source_registry(ctx, fallback_names)
    previous = None
    last_failure = None

    for source_name in music_sources:
        source = registry[source_name]

        if previous is not None and previous.transition_message:
            _report.muted(previous.transition_message)

        selection = source.find(
            metadata["artist"],
            metadata["title"],
            metadata.get("duration"),
            previous=previous,
            metadata=metadata,
        )

        if selection is None:
            continue

        if isinstance(selection, SourceOutcome):
            previous = selection
            last_failure = selection
            continue

        download = _download_and_tag(selection, ctx, source.download)

        if download.ok or not download.download_failed:
            return download.ok, download.reason

        previous = source.classify_download_failure(selection, download.reason)
        last_failure = previous

    if last_failure is None:
        return False, "no music sources enabled"

    return last_failure.ok, last_failure.reason


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

    return _try_music_sources(
        metadata,
        ctx,
        (input_artist, input_title),
    )


__all__ = ["_soundcloud_artwork", "process_song"]
