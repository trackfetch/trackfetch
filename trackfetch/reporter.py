# SPDX-License-Identifier: GPL-3.0-or-later
"""User-facing output: the single place that talks in colors."""

from . import colors


class Reporter:
    """Prints user-facing status lines.

    All formatting lives here so the pipeline and providers stay free of
    ``print(colors....)`` calls. The messages are byte-for-byte the ones the
    CLI has always produced.
    """

    @staticmethod
    def info(message: str):
        print(message)

    @staticmethod
    def skip(message: str):
        print(f"{colors.skip('SKIP:')} {message}")

    @staticmethod
    def fail(message: str):
        print(f"{colors.error('FAILED:')} {message}")

    @staticmethod
    def fail_raw(message: str):
        # "FAILED:" is already part of the message (SoundCloud reasons).
        print(colors.error(message))

    @staticmethod
    def success(message: str):
        print(f"{colors.success(message)}")

    @staticmethod
    def label(label: str, message: str):
        print(f"{colors.label(label)} {message}")

    @staticmethod
    def label_plain(label: str, message: str):
        print(f"{colors.label(label)} {colors.muted(message)}")

    @staticmethod
    def label_success(label: str, message: str):
        print(f"{colors.label(label)} {colors.success(message)}")

    @staticmethod
    def muted(message: str):
        print(colors.muted(message))

    @staticmethod
    def warning(message: str):
        print(colors.warning(message))
