# SPDX-License-Identifier: GPL-3.0-or-later
"""Named scoring weights and thresholds, frozen for stability.

Each dataclass groups the magic numbers previously inlined in the scoring
functions. Defaults equal the historical literals, so results are unchanged.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class YoutubeScoring:
    """Weights and bonuses for :func:`trackfetch.youtube.score_youtube_result`."""

    # Base blend: title vs artist evidence.
    title_weight: float = 0.70
    artist_weight: float = 0.30

    # A "- Topic" channel means YouTube itself uploaded the track.
    topic_channel_bonus: float = 0.15
    # Any other channel similar to the artist is weaker evidence.
    channel_bonus: float = 0.10
    # Channel similarity at which the channel bonus applies.
    channel_bonus_min_score: float = 0.6

    # Marker bonuses seen in the upload title.
    official_audio_bonus: float = 0.08
    audio_bonus: float = 0.03

    # Penalty per noise marker (cover, karaoke, nightcore, ...).
    bad_word_penalty: float = 0.20

    # Duration proximity bonuses.
    close_duration_bonus: float = 0.05
    close_duration_limit: float = 3
    near_duration_bonus: float = 0.02
    near_duration_limit: float = 10


@dataclass(frozen=True)
class SoundcloudScoring:
    """Weights and thresholds for SoundCloud candidate scoring."""

    # The blend from the task brief: title 40%, artist 30%, duration 20%,
    # additional metadata 10%.
    title_weight: float = 0.40
    artist_weight: float = 0.30
    duration_weight: float = 0.20
    extra_weight: float = 0.10

    # Duration is neutral when either side lacks it: this substitutes for it.
    neutral_duration_score: float = 0.5

    # Duration similarity tiers.
    duration_exact_limit: float = 3
    duration_exact_score: float = 1.0
    duration_near_score: float = 0.9
    duration_close_ratio_limit: float = 0.10
    duration_close_score: float = 0.6
    duration_far_ratio_limit: float = 0.20
    duration_far_score: float = 0.3

    # Extra evidence thresholds.
    explicit_artist_min_score: float = 0.6
    uploader_evidence_score: float = 0.7
    raw_title_evidence_score: float = 0.4

    # Variant scoring penalties.
    leading_words_penalty: float = 0.35
    trailing_words_penalty: float = 0.7
    trailing_words_limit: float = 3
    ordered_words_discount: float = 0.75
    latin_similarity_floor: float = 0.8

    # Containment boost for an explicit artist field or a title prefix.
    contains_artist_score: float = 0.92

    # Fuzzy-window acceptance threshold for transliteration variance.
    fuzzy_window_threshold: float = 0.8

    # A candidate must reach this score before it is downloaded.
    min_title_score: float = 0.35


@dataclass(frozen=True)
class MetadataScoring:
    """Weights for metadata provider candidate scoring."""

    title_weight: float = 0.70
    artist_weight: float = 0.30


@dataclass(frozen=True)
class LyricsScoring:
    """Duration bonuses for ranking LRCLIB search results."""

    close_duration_bonus: float = 0.05
    close_duration_limit: float = 3
    near_duration_bonus: float = 0.02
    near_duration_limit: float = 10


DEFAULT_YOUTUBE_SCORING = YoutubeScoring()
DEFAULT_SOUNDCLOUD_SCORING = SoundcloudScoring()
DEFAULT_METADATA_SCORING = MetadataScoring()
DEFAULT_LYRICS_SCORING = LyricsScoring()
