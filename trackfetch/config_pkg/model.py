# SPDX-License-Identifier: GPL-3.0-or-later
"""The resolved source configuration and its presentation helpers."""

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
    SOUNDCLOUD_DEFAULT_ENABLED,
    SOUNDCLOUD_DEFAULT_TRIGGER,
    SOUNDCLOUD_MIN_MARGIN,
    SOUNDCLOUD_MIN_SCORE,
    VOCALOID_HINTS,
)
from ..enums import MusicSource
from ..ui import colors

_SOURCE_OPTIONS = {
    "match_threshold": DEFAULT_MATCH_THRESHOLD,
    "title_threshold": DEFAULT_TITLE_THRESHOLD,
    "none_selected": False,
    "lyrics_enabled": LYRICS_DEFAULT_ENABLED,
    "cache_enabled": CACHE_DEFAULT_ENABLED,
    "lyrics_type": DEFAULT_LYRICS_TYPE,
    "soundcloud_enabled": SOUNDCLOUD_DEFAULT_ENABLED,
    "soundcloud_min_score": SOUNDCLOUD_MIN_SCORE,
    "soundcloud_min_margin": SOUNDCLOUD_MIN_MARGIN,
    "soundcloud_trigger": SOUNDCLOUD_DEFAULT_TRIGGER,
    "soundcloud_ambiguous": SOUNDCLOUD_DEFAULT_AMBIGUOUS,
    "music_sources": None,
}


class SourceConfig:
    """The resolved, immutable-in-practice source configuration for one run.

    ``music_sources`` is the single source of truth for the music provider
    priority. ``youtube_enabled`` and ``soundcloud_enabled`` are computed
    properties kept for the public facade; assigning to them raises.

    The optional settings stay available under their historical keyword names
    and positional order. ``*options``/``**overrides`` keep the constructor
    signature readable while accepting every old call unchanged.
    """

    def __init__(
        self,
        metadata_sources,
        youtube_enabled=True,
        providers=None,
        *options,
        **overrides,
    ):
        if len(options) > len(_SOURCE_OPTIONS):
            raise TypeError(
                "SourceConfig() takes at most "
                f"{3 + len(_SOURCE_OPTIONS)} positional arguments"
            )

        values = dict(zip(_SOURCE_OPTIONS, options, strict=False))

        for name in values:
            if name in overrides:
                raise TypeError(
                    "SourceConfig() got multiple values for argument "
                    f"'{name}'"
                )

        unknown = set(overrides) - set(_SOURCE_OPTIONS)

        if unknown:
            raise TypeError(
                "SourceConfig() got an unexpected keyword argument "
                f"'{sorted(unknown)[0]}'"
            )

        values = {**_SOURCE_OPTIONS, **values, **overrides}
        self.metadata_sources = list(metadata_sources)
        self.providers = providers if providers is not None else {}
        self.match_threshold = values["match_threshold"]
        self.title_threshold = values["title_threshold"]
        self.none_selected = bool(values["none_selected"])
        self.lyrics_enabled = bool(values["lyrics_enabled"])
        self.cache_enabled = bool(values["cache_enabled"])
        self.lyrics_type = values["lyrics_type"]
        self.soundcloud_min_score = values["soundcloud_min_score"]
        self.soundcloud_min_margin = values["soundcloud_min_margin"]
        self.soundcloud_trigger = values["soundcloud_trigger"]
        self.soundcloud_ambiguous = values["soundcloud_ambiguous"]

        music_sources = values["music_sources"]

        if music_sources is not None:
            self.music_sources = list(music_sources)
        else:
            # Keep direct SourceConfig users compatible: derive the priority
            # from the two legacy enabled flags.
            self.music_sources = [
                name
                for name, enabled in (
                    (MusicSource.YOUTUBE.value, youtube_enabled),
                    (MusicSource.SOUNDCLOUD.value, values["soundcloud_enabled"]),
                )
                if enabled
            ]

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
