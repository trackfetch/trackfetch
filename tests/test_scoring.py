# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the shared scoring constants and string-based enums."""

import trackfetch
from trackfetch.enums import AudioFormat, MusicSource
from trackfetch.scoring import (
    DEFAULT_LYRICS_SCORING,
    DEFAULT_METADATA_SCORING,
    DEFAULT_SOUNDCLOUD_SCORING,
    DEFAULT_YOUTUBE_SCORING,
)


class TestEnums:
    def test_audio_format_values_match_legacy_strings(self):
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.M4A.value == "m4a"
        assert AudioFormat.OPUS.value == "opus"

    def test_music_source_values_match_legacy_strings(self):
        assert MusicSource.YOUTUBE.value == "youtube"
        assert MusicSource.SOUNDCLOUD.value == "soundcloud"

    def test_string_equality_keeps_config_compatible(self):
        assert AudioFormat.MP3 == "mp3"
        assert MusicSource.SOUNDCLOUD == "soundcloud"


class TestYoutubeScoringDefaults:
    def test_defaults_equal_historical_numbers(self):
        scoring = DEFAULT_YOUTUBE_SCORING
        assert scoring.title_weight == 0.70
        assert scoring.artist_weight == 0.30
        assert scoring.topic_channel_bonus == 0.15
        assert scoring.channel_bonus == 0.10
        assert scoring.channel_bonus_min_score == 0.6
        assert scoring.official_audio_bonus == 0.08
        assert scoring.audio_bonus == 0.03
        assert scoring.bad_word_penalty == 0.20
        assert scoring.close_duration_bonus == 0.05
        assert scoring.close_duration_limit == 3
        assert scoring.near_duration_bonus == 0.02
        assert scoring.near_duration_limit == 10

    def test_frozen(self):
        try:
            DEFAULT_YOUTUBE_SCORING.title_weight = 1.0
        except Exception:
            pass
        else:
            raise AssertionError("YoutubeScoring must be frozen")


class TestSoundcloudScoringDefaults:
    def test_defaults_equal_historical_numbers(self):
        scoring = DEFAULT_SOUNDCLOUD_SCORING
        assert scoring.title_weight == 0.40
        assert scoring.artist_weight == 0.30
        assert scoring.duration_weight == 0.20
        assert scoring.extra_weight == 0.10
        assert scoring.neutral_duration_score == 0.5
        assert scoring.duration_exact_score == 1.0
        assert scoring.duration_near_score == 0.9
        assert scoring.duration_close_score == 0.6
        assert scoring.duration_far_score == 0.3
        assert scoring.contains_artist_score == 0.92
        assert scoring.min_title_score == 0.35


class TestMetadataAndLyricsScoringDefaults:
    def test_metadata_defaults(self):
        assert DEFAULT_METADATA_SCORING.title_weight == 0.70
        assert DEFAULT_METADATA_SCORING.artist_weight == 0.30

    def test_lyrics_defaults(self):
        assert DEFAULT_LYRICS_SCORING.close_duration_bonus == 0.05
        assert DEFAULT_LYRICS_SCORING.close_duration_limit == 3
        assert DEFAULT_LYRICS_SCORING.near_duration_bonus == 0.02
        assert DEFAULT_LYRICS_SCORING.near_duration_limit == 10


class TestFacadeExports:
    def test_new_names_are_exported(self):
        for name in (
            "AudioFormat",
            "MusicSource",
            "YoutubeScoring",
            "SoundcloudScoring",
            "MetadataScoring",
            "LyricsScoring",
        ):
            assert hasattr(trackfetch, name)
