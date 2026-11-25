# SPDX-License-Identifier: GPL-3.0-or-later
"""The result of one pipeline attempt: a status plus a machine reason."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    """Outcome of one download attempt.

    ``status`` answers "did we get a file"; ``reason`` is the short
    machine-readable string written to failed.txt (or a skip marker such as
    ``exists``). ``download_failed`` additionally marks yt-dlp returning no
    audio so the caller can decide whether the failure is worth a fallback.
    """

    ok: bool
    reason: str
    download_failed: bool = False

    def __iter__(self):
        # Backwards compatibility with the historical (ok, reason) tuple.
        return iter((self.ok, self.reason))
