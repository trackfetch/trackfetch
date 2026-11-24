# SPDX-License-Identifier: GPL-3.0-or-later
"""Exceptions raised across TrackFetch.

The hierarchy starts at :class:`TrackFetchError` so callers can catch every
domain error with a single clause while still letting programming errors
(KeyboardInterrupt, SystemExit, genuine bugs) through.
"""


class TrackFetchError(Exception):
    """Base class for every domain-specific TrackFetch failure."""


class ProviderError(TrackFetchError):
    """A provider request failed for a real, retryable reason."""


class ProviderAuthError(ProviderError):
    """A provider rejected the credentials."""


class YoutubeSearchError(TrackFetchError):
    """yt-dlp search exited with a non-zero status."""


class SoundcloudError(TrackFetchError):
    """A SoundCloud search or metadata request failed."""


class TaggingError(TrackFetchError):
    """Writing metadata into the audio file failed."""


class CoverError(TrackFetchError):
    """Downloading or decoding cover art failed."""


class ConfigError(TrackFetchError, ValueError):
    """An invalid configuration value was supplied.

    Inherits from ``ValueError`` so historical ``except ValueError`` call
    sites (the CLI error handler, config tests) keep working unchanged.
    """
