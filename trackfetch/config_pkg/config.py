# SPDX-License-Identifier: GPL-3.0-or-later
"""Source configuration: provider priority, thresholds and promotion rules.

Kept as the import location used by the rest of the package and the public
facade. The implementation lives in :mod:`model`, :mod:`loader`,
:mod:`builder` and :mod:`validate`.
"""

from .builder import build_source_config
from .loader import (
    config_str_value,
)
from .model import (
    LyricsOptions,
    SoundcloudPolicy,
    SourceConfig,
    Thresholds,
    effective_metadata_sources,
    format_source_list,
    has_vocadb_hint,
)
from .validate import (
    normalize_disable_sources,
    normalize_metadata_sources,
    normalize_music_sources,
    parse_bool,
    parse_interval,
    parse_provider_options,
    split_source_names,
    threshold_value,
)

__all__ = [
    "LyricsOptions",
    "SoundcloudPolicy",
    "SourceConfig",
    "Thresholds",
    "build_source_config",
    "config_str_value",
    "effective_metadata_sources",
    "format_source_list",
    "has_vocadb_hint",
    "normalize_disable_sources",
    "normalize_metadata_sources",
    "normalize_music_sources",
    "parse_bool",
    "parse_interval",
    "parse_provider_options",
    "split_source_names",
    "threshold_value",
]
