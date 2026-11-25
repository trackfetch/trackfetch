# SPDX-License-Identifier: GPL-3.0-or-later
"""Concrete music sources and the registry used by the pipeline."""

from dataclasses import dataclass, field

from .. import colors
from ..audio.soundcloud.selection import describe_failure, trigger_allows
from ..config_pkg.constants import (
    SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    SOUNDCLOUD_DEFAULT_TRIGGER,
)
from ..enums import MusicSource
from ..errors import YoutubeSearchError
from ..protocols import AudioSource
from .reporter import Reporter

_report = Reporter()


@dataclass
class SourceOutcome:
    """A failed source attempt plus the facts later triggers need."""

    ok: bool
    reason: str
    download_failed: bool = False
    age_restricted: bool = False
    blocked: bool = False
    transition_message: str = None


@dataclass
class SourceSelection:
    """One chosen track that is ready to download."""

    url: str
    video: dict
    metadata: dict = field(repr=False)
    allow_thumbnails: bool = True


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


class YoutubeSource:
    """YouTube search and download, wrapped in the AudioSource protocol."""

    name = MusicSource.YOUTUBE.value

    def __init__(self, ctx, find_func, download_func, probe_func, module):
        self.ctx = ctx
        self._find = find_func
        self._download = download_func
        self._probe = probe_func
        self._module = module

    def find(self, artist, title, duration=None, previous=None, metadata=None):
        """Return a selection, or a failure with its trigger facts."""
        self._module.LAST_SEARCH_HAD_CANDIDATES = False

        try:
            video = self._find(artist, title, duration)

        except YoutubeSearchError as error:
            _report.fail(f"yt-dlp search failed: {error}")
            return SourceOutcome(False, "yt-dlp search failed")

        if not video:
            if self._module.LAST_SEARCH_HAD_CANDIDATES:
                reason = "no confident YouTube match"
                _report.fail("No confident YouTube match")

            else:
                reason = "no YouTube result"
                _report.fail("No YouTube result")

            return SourceOutcome(False, reason)

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
            return SourceOutcome(False, "invalid YouTube result")

        return SourceSelection(
            url=video_url,
            video=video,
            metadata=metadata,
        )

    def download(self, url, temp_dir, audio_format, audio_quality=None):
        """Download one selected video."""
        return self._download(url, temp_dir, audio_format, audio_quality)

    def classify_download_failure(self, selection, reason):
        """Attach age/bot facts to a yt-dlp download failure."""
        # The download's own stderr is the most reliable signal: a bot check
        # often lets --dump-single-json through and only fails here. Fall back
        # to the metadata probe for yt-dlp versions that stay quiet.
        download_error = self._module.LAST_DOWNLOAD_ERROR
        age_restricted = self._module.is_age_restriction_error(download_error)
        blocked = self._module.is_bot_check_error(download_error)

        if not age_restricted and not blocked:
            age_restricted = self._probe(selection.url)

        return SourceOutcome(
            False,
            reason,
            download_failed=True,
            age_restricted=age_restricted,
            blocked=blocked,
        )


class SoundcloudSource:
    """SoundCloud search and download, wrapped in the AudioSource protocol."""

    name = MusicSource.SOUNDCLOUD.value

    def __init__(self, ctx, module, download_func, fallback_names=None):
        self.ctx = ctx
        self._module = module
        self._download = download_func
        self._fallback_names = fallback_names

    @property
    def _config(self):
        return self.ctx.source_config

    def _announce(self, previous):
        if previous is None:
            _report.muted(
                "Searching SoundCloud as the primary music source."
            )

        elif previous.age_restricted is True:
            _report.warning(
                "AGE-RESTRICTED: YouTube requires sign-in for this video."
            )

        else:
            _report.muted(
                "YouTube had no usable result; looking for the track "
                "on SoundCloud."
            )

    def _accepts(self, previous):
        if previous is None:
            return True

        return trigger_allows(
            getattr(
                self._config,
                "soundcloud_trigger",
                SOUNDCLOUD_DEFAULT_TRIGGER,
            ),
            previous.reason,
            previous.age_restricted,
            previous.blocked,
        )

    def find(self, artist, title, duration=None, previous=None, metadata=None):
        """Return a selection, a failure, or None when the trigger declines."""
        if not self._accepts(previous):
            return None

        self._announce(previous)

        source_config = self._config
        result = self._module.find_soundcloud_fallback(
            artist,
            title,
            duration,
            enabled=source_config.soundcloud_enabled,
            min_score=source_config.soundcloud_min_score,
            min_margin=source_config.soundcloud_min_margin,
            ambiguous=getattr(
                source_config,
                "soundcloud_ambiguous",
                SOUNDCLOUD_DEFAULT_AMBIGUOUS,
            ),
            fallback_names=self._fallback_names,
        )

        if not result.selected or not result.candidate:
            return SourceOutcome(
                False,
                describe_failure(result),
                transition_message=(
                    "SoundCloud did not produce a track; trying YouTube."
                ),
            )

        # The search results were already enriched with --dump-single-json
        # metadata, so the selected candidate is verified without another call.
        candidate = result.candidate
        blocked = self._module.blocked_reason(candidate)

        if blocked:
            _report.fail_raw(f"FAILED: SoundCloud track {blocked}")
            return SourceOutcome(
                False,
                f"SoundCloud {blocked}",
                transition_message=(
                    "SoundCloud did not produce a track; trying YouTube."
                ),
            )

        preview = self._module.preview_reason(
            candidate,
            duration,
        )

        if preview:
            _report.fail_raw(f"FAILED: SoundCloud track is {preview}")
            return SourceOutcome(
                False,
                f"SoundCloud {preview}",
                transition_message=(
                    "SoundCloud did not produce a track; trying YouTube."
                ),
            )

        webpage_url = candidate.get("webpage_url")

        if not webpage_url:
            _report.fail("Invalid SoundCloud result")
            return SourceOutcome(
                False,
                "invalid SoundCloud result",
                transition_message=(
                    "SoundCloud did not produce a track; trying YouTube."
                ),
            )

        _report.label(
            "Selected:",
            f"{candidate.get('title', 'Unknown')} "
            f"{colors.muted('(SoundCloud)')}",
        )

        # Keep the provider artwork; only add SoundCloud art when the metadata
        # source had none, so the tags stay consistent with the rest of the run.
        tagged_metadata = metadata

        if not (metadata or {}).get("cover_url"):
            artwork = _soundcloud_artwork(candidate)

            if artwork:
                tagged_metadata = dict(metadata)
                tagged_metadata["cover_url"] = artwork

        return SourceSelection(
            url=webpage_url,
            video={
                "title": candidate.get("title"),
                "thumbnails": candidate.get("thumbnails"),
                "thumbnail": candidate.get("thumbnail"),
            },
            metadata=tagged_metadata,
            # SoundCloud artwork replaces the YouTube thumbnail fallback.
            allow_thumbnails=False,
        )

    def download(self, url, temp_dir, audio_format, audio_quality=None):
        """Download one selected SoundCloud track."""
        return self._download(url, temp_dir, audio_format, audio_quality)

    def classify_download_failure(self, selection, reason):
        """A SoundCloud download failure is never itself retried."""
        return SourceOutcome(
            False,
            reason,
            download_failed=True,
            transition_message=(
                "SoundCloud did not produce a track; trying YouTube."
            ),
        )


def build_registry(
    ctx,
    *,
    youtube_module,
    soundcloud_module,
    find_youtube,
    download_audio,
    probe_age_restriction,
    fallback_names=None,
):
    """Build the {MusicSource: AudioSource} registry for one song."""
    return {
        MusicSource.YOUTUBE: YoutubeSource(
            ctx,
            find_youtube,
            download_audio,
            probe_age_restriction,
            youtube_module,
        ),
        MusicSource.SOUNDCLOUD: SoundcloudSource(
            ctx,
            soundcloud_module,
            download_audio,
            fallback_names=fallback_names,
        ),
    }


def as_audio_source(source) -> AudioSource:
    """Runtime assertion helper documenting the AudioSource contract."""
    return source


__all__ = [
    "SoundcloudSource",
    "SourceOutcome",
    "SourceSelection",
    "YoutubeSource",
    "as_audio_source",
    "build_registry",
]
