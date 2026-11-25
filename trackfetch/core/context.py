# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-song execution context shared by the pipeline functions."""

from dataclasses import dataclass
from pathlib import Path

from ..config_pkg.constants import DEFAULT_AUDIO_QUALITY, DEFAULT_FORMAT


@dataclass(frozen=True)
class RunContext:
    """Everything one song's download needs, grouped in one object.

    Replaces the previous 10-11 parameter function signatures. ``output``,
    ``title_only``, ``audio_format`` and ``audio_quality`` come from the CLI;
    ``source_config`` and ``runtime`` from the run setup; ``lyrics_type`` is
    already resolved (never None).
    """

    output: Path
    title_only: bool
    audio_format: str = DEFAULT_FORMAT
    audio_quality: int = DEFAULT_AUDIO_QUALITY
    source_config: object = None
    runtime: object = None
    lyrics_type: str = "inline"
