# SPDX-License-Identifier: GPL-3.0-or-later
"""YouTube candidate scoring and query planning."""

import re
import unicodedata

from unidecode import unidecode

from ...matching import MIN_ARTIST_SIMILARITY, normalize, similarity
from ...scoring import DEFAULT_YOUTUBE_SCORING


def transliterate(text) -> str:
    """Return a Latin-script form, dropping the apostrophes Unidecode adds.

    Unidecode renders some Cyrillic letters with an apostrophe, turning the
    transliteration into separate words after normalization. Removing the
    apostrophes keeps the artist name as one token.
    """
    return unidecode(text or "").replace("'", "")


def _forms(text):
    """Return the original and Latin-script forms of a string."""
    text = text or ""
    return (text, transliterate(text))


def cross_script_similarity(a: str, b: str) -> float:
    """Compare strings in their original scripts and in Latin."""
    return max(
        similarity(a, b),
        similarity(transliterate(a), transliterate(b)),
    )


def _contains_artist(artist: str, text: str) -> bool:
    """Whether the artist appears in text in either the original script or Latin."""
    if not artist or not text:
        return False

    for artist_form, text_form in zip(_forms(artist), _forms(text), strict=False):
        normalized_artist = normalize(artist_form)
        normalized_text = normalize(text_form)

        if normalized_artist and normalized_artist in normalized_text:
            return True

    return False


def _artist_score(artist: str, title: str, video_title: str, channel: str):
    """Compare the artist with the title, the channel and their Latin forms."""
    video_title = video_title or ""
    channel = channel or ""

    best = max(
        similarity(artist, video_title),
        similarity(transliterate(artist), transliterate(video_title)),
    )
    title_boost = 0.0

    # Many videos are "Artist - Song" or "Artist Song (Official Video)". When
    # the normalized title starts with the artist, that is a strong artist
    # signal, and the title is compared with the leftover words. Transcoding
    # to Latin makes this work across scripts, so a Latin artist name can
    # match a Cyrillic "Artist - Song" upload. A channel name like
    # "Metal Family “Artist - Song»" does not start with the artist, so it is
    # not inflated.
    for artist_form, title_form in zip(_forms(artist), _forms(video_title), strict=False):
        normalized_artist = normalize(artist_form)
        normalized_video = normalize(title_form)

        if normalized_artist and normalized_video.startswith(normalized_artist):
            remainder = normalized_video[len(normalized_artist):].strip(" -")

            if remainder:
                best = 1.0
                title_boost = max(
                    title_boost,
                    similarity(title, remainder),
                    similarity(transliterate(title), remainder),
                )

    channel_score = 0.0

    if channel:
        channel_score = max(
            similarity(artist, channel),
            similarity(transliterate(artist), transliterate(channel)),
        )

        for artist_form, channel_form in zip(_forms(artist), _forms(channel), strict=False):
            normalized_artist = normalize(artist_form)
            normalized_channel = normalize(channel_form)

            if normalized_artist and normalized_channel.startswith(normalized_artist):
                channel_score = 1.0

    return max(best, channel_score), title_boost, channel_score


def duration_difference(video_duration, duration):
    if duration is None or video_duration is None:
        return None

    try:
        return abs(float(video_duration) - float(duration))

    except (TypeError, ValueError):
        return None


def _has_artist_evidence(video, artist: str, title: str, duration) -> bool:
    """Whether a title-only search result can be trusted.

    A query without the artist can return covers, other artists' songs with the
    same title, or audiobooks. The artist must appear in the title or channel,
    or the duration must be close to the expected one.
    """
    video_title = video.get("title", "")
    channel = video.get("channel") or video.get("uploader") or ""

    if _contains_artist(artist, video_title) or _contains_artist(artist, channel):
        return True

    difference = duration_difference(video.get("duration"), duration)

    return difference is not None and difference <= 5


def score_youtube_result(
    video,
    artist: str,
    title: str,
    duration=None,
    scoring=DEFAULT_YOUTUBE_SCORING,
):
    video_title = video.get("title", "")
    channel = video.get("channel") or video.get("uploader") or ""

    title_score = similarity(title, video_title)
    artist_score, title_boost, channel_score = _artist_score(
        artist,
        title,
        video_title,
        channel,
    )
    title_score = max(title_score, title_boost)

    score = (
        title_score * scoring.title_weight
        + artist_score * scoring.artist_weight
    )

    # A channel that matches the artist is extra evidence, and a "- Topic"
    # channel is the cleanest signal that YouTube itself uploaded the track.
    if channel and channel_score >= scoring.channel_bonus_min_score:
        if normalize(channel).endswith("topic"):
            score += scoring.topic_channel_bonus

        else:
            score += scoring.channel_bonus

    # Noise stripping is for matching. Bonus and penalty markers still need
    # to see the original words, including ones inside brackets.
    detected_video = unicodedata.normalize("NFC", video_title).lower()

    if "official audio" in detected_video:
        score += scoring.official_audio_bonus

    if "audio" in detected_video:
        score += scoring.audio_bonus

    bad_words = [
        "cover",
        "караоке",
        "karaoke",
        "nightcore",
        "sped up",
        "slowed",
        "remix",
        "reaction",
    ]

    for word in bad_words:
        # Whole words only: "Discovery" must not trigger "cover".
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", detected_video):
            score -= scoring.bad_word_penalty

    difference = duration_difference(video.get("duration"), duration)

    if difference is not None:
        if difference <= scoring.close_duration_limit:
            score += scoring.close_duration_bonus

        elif difference <= scoring.near_duration_limit:
            score += scoring.near_duration_bonus

    return score


def search_queries(artist: str, title: str):
    """Return the query ladder: artist+title, then title-only variants."""
    queries = []

    for query in (f"{artist} {title}", title, f"{title} Topic"):
        query = " ".join((query or "").split())

        if query and query not in queries:
            queries.append(query)

    return queries


def details_artist_names(details):
    names = []
    artist = details.get("artist")

    if artist:
        names.append(artist)

    artists = details.get("artists")

    if isinstance(artists, list):
        names.extend(name for name in artists if name)

    for key in ("channel", "uploader"):
        value = details.get(key)

        if value:
            names.append(value)

    return names


def details_artist_similarity(artist, details):
    return max(
        (
            cross_script_similarity(artist, name)
            for name in details_artist_names(details)
        ),
        default=0.0,
    )


def has_artist_evidence(video, artist: str, title: str, duration) -> bool:
    """Public wrapper used by the search orchestration."""
    return _has_artist_evidence(video, artist, title, duration)


def artist_matches_details(artist, details) -> bool:
    """Whether the details payload names the requested artist convincingly."""
    return details_artist_similarity(artist, details) >= MIN_ARTIST_SIMILARITY


__all__ = [
    "_contains_artist",
    "artist_matches_details",
    "details_artist_similarity",
    "duration_difference",
    "has_artist_evidence",
    "score_youtube_result",
    "search_queries",
    "transliterate",
]
