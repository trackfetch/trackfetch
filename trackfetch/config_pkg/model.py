# SPDX-License-Identifier: GPL-3.0-or-later
"""The resolved source configuration and its presentation helpers."""

from dataclasses import dataclass, field

from ..config_pkg.constants import (
    ARTWORK_FALLBACKS,
    CACHE_DEFAULT_ENABLED,
    CJK_RE,
    DEFAULT_LYRICS_TYPE,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_TITLE_THRESHOLD,
    LYRICS_DEFAULT_ENABLED,
    METADATA_PROVIDERS,
    MUSIC_PROVIDERS,
    SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    SOUNDCLOUD_DEFAULT_TRIGGER,
    SOUNDCLOUD_MIN_MARGIN,
    SOUNDCLOUD_MIN_SCORE,
    VOCALOID_HINTS,
)
from ..enums import MusicSource
from ..ui import colors


@dataclass(frozen=True)
class Thresholds:
    """Score thresholds for metadata matching."""

    match: float = DEFAULT_MATCH_THRESHOLD
    title: float = DEFAULT_TITLE_THRESHOLD


@dataclass(frozen=True)
class SoundcloudPolicy:
    """When and how the SoundCloud fallback is allowed to run."""

    min_score: float = SOUNDCLOUD_MIN_SCORE
    min_margin: float = SOUNDCLOUD_MIN_MARGIN
    trigger: str = SOUNDCLOUD_DEFAULT_TRIGGER
    ambiguous: str = SOUNDCLOUD_DEFAULT_AMBIGUOUS


@dataclass(frozen=True)
class LyricsOptions:
    """Lyrics embedding and metadata cache toggles."""

    enabled: bool = LYRICS_DEFAULT_ENABLED
    type: str = DEFAULT_LYRICS_TYPE
    cache: bool = CACHE_DEFAULT_ENABLED


@dataclass
class SourceConfig:
    """The resolved source configuration for one run.

    ``music_sources`` is the single source of truth for the music provider
    priority. ``youtube_enabled`` and ``soundcloud_enabled`` are computed
    properties kept for the public facade.

    The constructor only accepts the declared fields, so a misspelled keyword
    raises ``TypeError`` instead of being silently ignored. The flat accessors
    (``match_threshold``, ``soundcloud_trigger`` and friends) remain available
    as read-only properties for existing consumers.
    """

    metadata_sources: list
    music_sources: list
    providers: dict = field(default_factory=dict)
    thresholds: Thresholds = field(default_factory=Thresholds)
    soundcloud: SoundcloudPolicy = field(default_factory=SoundcloudPolicy)
    lyrics: LyricsOptions = field(default_factory=LyricsOptions)
    none_selected: bool = False

    def __post_init__(self):
        self.metadata_sources = list(self.metadata_sources)
        self.music_sources = list(self.music_sources)
        self.providers = self.providers if self.providers is not None else {}
        self.none_selected = bool(self.none_selected)

    @property
    def match_threshold(self) -> float:
        return self.thresholds.match

    @property
    def title_threshold(self) -> float:
        return self.thresholds.title

    @property
    def lyrics_enabled(self) -> bool:
        return self.lyrics.enabled

    @property
    def cache_enabled(self) -> bool:
        return self.lyrics.cache

    @property
    def lyrics_type(self) -> str:
        return self.lyrics.type

    @property
    def soundcloud_min_score(self) -> float:
        return self.soundcloud.min_score

    @property
    def soundcloud_min_margin(self) -> float:
        return self.soundcloud.min_margin

    @property
    def soundcloud_trigger(self) -> str:
        return self.soundcloud.trigger

    @property
    def soundcloud_ambiguous(self) -> str:
        return self.soundcloud.ambiguous

    @property
    def youtube_enabled(self) -> bool:
        return MusicSource.YOUTUBE.value in self.music_sources

    @property
    def soundcloud_enabled(self) -> bool:
        return MusicSource.SOUNDCLOUD.value in self.music_sources

    def is_music_enabled(self, name: str) -> bool:
        return name in self.music_sources

    @property
    def primary_music_source(self):
        return next(iter(self.music_sources), None)

    def interval(self, name: str) -> float:
        return self.providers[name]["min_interval"]

    def is_enabled(self, name: str) -> bool:
        return bool(self.providers[name].get("enabled"))


def has_vocadb_hint(artist: str, title: str) -> bool:
    text = f"{artist} {title}"
    lowered = text.lower()

    if CJK_RE.search(text):
        return True

    return any(hint in lowered for hint in VOCALOID_HINTS)


def effective_metadata_sources(config: SourceConfig, artist: str, title: str):
    """Apply the temporary VocaDB promotion without changing the config."""
    sources = [
        name
        for name in config.metadata_sources
        if config.is_enabled(name)
    ]
    vocadb = config.providers["vocadb"]

    if config.none_selected:
        # An explicit empty list such as `-s none` stays empty.
        return []

    if not has_vocadb_hint(artist, title) or vocadb.get("disabled"):
        return sources

    if "vocadb" in sources:
        sources.remove("vocadb")

    return ["vocadb", *sources]


def _status(enabled):
    """Return the shared enabled/disabled status column."""
    status_text = "enabled" if enabled else "disabled"
    return (
        colors.success(f"{status_text:<9}")
        if enabled
        else colors.muted(f"{status_text:<9}")
    )


def _music_lines(config, primary):
    lines = []

    for name in MUSIC_PROVIDERS:
        enabled = config.is_music_enabled(name)
        role = ""

        if enabled:
            role = " (primary)" if name == primary else " (fallback)"

        lines.append(
            f"  {colors.accent(f'{name:<12}')} {_status(enabled)} "
            f"credentials: {colors.muted('not required  ')}"
            f"{colors.muted(role.strip())}"
        )

    return lines


def _metadata_lines(config):
    lines = []

    for name in METADATA_PROVIDERS:
        entry = config.providers[name]
        enabled = bool(entry.get("enabled"))
        credentials = "required" if name == "spotify" else "not required"
        details = [f"min_interval={entry['min_interval']}s"]

        if name == "itunes":
            details.insert(0, f"country={entry.get('country', 'us')}")

        lines.append(
            f"  {colors.accent(f'{name:<12}')} {_status(enabled)} "
            f"credentials: {colors.muted(f'{credentials:<13}')} "
            f"{colors.muted(', '.join(details))}"
        )

    return lines


def _artwork_lines(config):
    lines = []
    enabled = bool(config.youtube_enabled)

    for name in ARTWORK_FALLBACKS:
        lines.append(
            f"  {colors.accent(f'{name:<12}')} {_status(enabled)} "
            f"credentials: {colors.muted('not required  ')}"
            f"{colors.muted('used when metadata has no artwork')}"
        )

    return lines


def _soundcloud_label(config, primary):
    trigger_labels = {
        "age": "age-restricted YouTube only",
        "blocked": "age restriction or YouTube login wall",
        "age-or-missing": "blocked, or no YouTube match",
        "any": "any failed YouTube search or download",
    }

    if not config.soundcloud_enabled:
        return colors.muted("disabled")

    if primary == MusicSource.SOUNDCLOUD.value:
        return colors.success(
            "enabled (primary"
            + (
                "; YouTube fallback on failure)"
                if config.youtube_enabled
                else ")"
            )
        )

    return colors.success(
        "enabled ("
        + trigger_labels.get(
            config.soundcloud_trigger,
            config.soundcloud_trigger,
        )
        + ")"
    )


def _summary_lines(config, primary):
    lyrics = (
        colors.success("enabled (LRCLIB, all formats)")
        if config.lyrics_enabled
        else colors.muted("disabled")
    )
    cache = (
        colors.success("enabled (metadata-cache.json)")
        if config.cache_enabled
        else colors.muted("disabled")
    )
    ambiguous = (
        colors.success("take the best result")
        if getattr(config, "soundcloud_ambiguous", "skip") == "best"
        else colors.muted("ask on a terminal, otherwise skip")
    )
    return [
        "",
        f"{colors.label('Music priority:')} "
        + colors.accent(", ".join(config.music_sources) or "none"),
        f"{colors.label('Metadata priority:')} "
        + colors.accent(", ".join(config.metadata_sources) or "none"),
        f"{colors.label('Match threshold:')} {config.match_threshold}",
        f"{colors.label('Title threshold:')} {config.title_threshold}",
        f"{colors.label('Lyrics embedding:')} {lyrics}",
        f"{colors.label('Metadata cache:')} {cache}",
        f"{colors.label('SoundCloud fallback:')} "
        + _soundcloud_label(config, primary),
        f"{colors.label('SoundCloud ambiguity:')} {ambiguous}",
    ]


def format_source_list(config: SourceConfig) -> str:
    primary = config.primary_music_source
    lines = [
        colors.heading("Available sources:"),
        "",
        colors.heading("Music providers:"),
        *_music_lines(config, primary),
        "",
        colors.heading("Metadata providers:"),
        *_metadata_lines(config),
        "",
        colors.heading("Artwork fallbacks:"),
        *_artwork_lines(config),
        *_summary_lines(config, primary),
    ]
    return "\n".join(lines)
