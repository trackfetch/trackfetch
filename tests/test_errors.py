# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the TrackFetch exception hierarchy."""

import pytest

import trackfetch as m
from trackfetch.errors import (
    ConfigError,
    CoverError,
    ProviderAuthError,
    ProviderError,
    SoundcloudError,
    TaggingError,
    TrackFetchError,
    YoutubeSearchError,
)


class TestHierarchy:
    def test_every_error_derives_from_track_fetch_error(self):
        for error_type in (
            ProviderError,
            ProviderAuthError,
            YoutubeSearchError,
            SoundcloudError,
            TaggingError,
            CoverError,
            ConfigError,
        ):
            assert issubclass(error_type, TrackFetchError)

    def test_auth_error_is_provider_error(self):
        assert issubclass(ProviderAuthError, ProviderError)

    def test_config_error_is_value_error_for_backward_compatibility(self):
        # The CLI catches ValueError around config parsing.
        assert issubclass(ConfigError, ValueError)

    def test_facade_exports_every_name(self):
        for name in (
            "TrackFetchError",
            "ProviderError",
            "ProviderAuthError",
            "YoutubeSearchError",
            "SoundcloudError",
            "TaggingError",
            "CoverError",
            "ConfigError",
        ):
            assert hasattr(m, name)

    def test_tagging_error_is_raisable(self):
        with pytest.raises(TrackFetchError):
            raise TaggingError("bad tag")
