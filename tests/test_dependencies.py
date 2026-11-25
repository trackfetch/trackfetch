# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup checks for the FFmpeg command-line tools."""

import sys

import pytest

import trackfetch as m
from trackfetch.core import dependencies


def run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["trackfetch", *map(str, args)])
    m.main()


def missing(monkeypatch, *tools):
    monkeypatch.setattr(
        dependencies.shutil,
        "which",
        lambda name: None if name in tools else f"/usr/bin/{name}",
    )


class TestCheck:
    def test_both_present(self):
        assert dependencies.check_ffmpeg(
            which=lambda name: f"/usr/bin/{name}",
            platform="darwin",
        ) is None

    def test_missing_ffmpeg(self):
        problem = dependencies.check_ffmpeg(
            which=lambda name: None if name == "ffmpeg" else "/usr/bin/ffprobe",
            platform="darwin",
        )

        assert problem[0] == "ffmpeg was not found (ffprobe: found)"

    def test_missing_ffprobe(self):
        problem = dependencies.check_ffmpeg(
            which=lambda name: None if name == "ffprobe" else "/usr/bin/ffmpeg",
            platform="darwin",
        )

        assert problem[0] == "ffprobe was not found (ffmpeg: found)"

    def test_missing_both(self):
        problem = dependencies.check_ffmpeg(
            which=lambda name: None,
            platform="darwin",
        )

        assert problem[0] == "ffmpeg and ffprobe were not found"


class TestInstallHint:
    def test_darwin(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")

        hint = dependencies.ffmpeg_install_hint()

        assert "brew install ffmpeg" in hint
        assert "apt" not in hint
        assert "winget" not in hint

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        hint = dependencies.ffmpeg_install_hint()

        assert "apt install ffmpeg" in hint
        assert "dnf install ffmpeg" in hint
        assert "pacman -S ffmpeg" in hint
        assert "brew" not in hint

    def test_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")

        hint = dependencies.ffmpeg_install_hint()

        assert "winget install Gyan.FFmpeg" in hint
        assert "scoop" in hint
        assert "choco" in hint
        assert "brew" not in hint
        assert "apt" not in hint

    def test_other_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "freebsd")

        hint = dependencies.ffmpeg_install_hint()

        assert "https://ffmpeg.org/download.html" in hint
        assert "brew" not in hint
        assert "apt" not in hint
        assert "winget" not in hint


class TestCli:
    def test_missing_ffmpeg_exits_with_stderr(
        self, monkeypatch, capsys, tmp_path
    ):
        missing(monkeypatch, "ffmpeg")

        with pytest.raises(SystemExit) as exc:
            run_main(
                monkeypatch,
                "--track",
                "Artist - Title",
                "-o",
                tmp_path,
            )

        assert exc.value.code == 1
        lines = capsys.readouterr().err.splitlines()
        assert lines[0].startswith("ERROR: ffmpeg was not found")
        assert "(ffprobe: found)" in lines[0]

    def test_missing_ffprobe_exits_with_stderr(
        self, monkeypatch, capsys, tmp_path
    ):
        missing(monkeypatch, "ffprobe")

        with pytest.raises(SystemExit) as exc:
            run_main(
                monkeypatch,
                "--track",
                "Artist - Title",
                "-o",
                tmp_path,
            )

        assert exc.value.code == 1
        lines = capsys.readouterr().err.splitlines()
        assert lines[0].startswith("ERROR: ffprobe was not found")
        assert "(ffmpeg: found)" in lines[0]

    def test_missing_both_exits_with_stderr(
        self, monkeypatch, capsys, tmp_path
    ):
        missing(monkeypatch, "ffmpeg", "ffprobe")

        with pytest.raises(SystemExit) as exc:
            run_main(
                monkeypatch,
                "--track",
                "Artist - Title",
                "-o",
                tmp_path,
            )

        assert exc.value.code == 1
        lines = capsys.readouterr().err.splitlines()
        assert lines[0].startswith("ERROR: ffmpeg and ffprobe were not found")
        assert "found)" not in lines[0]

    @pytest.mark.parametrize("flag", ("--help", "-h", "--version", "-v"))
    def test_help_and_version_skip_the_check(
        self, monkeypatch, capsys, flag
    ):
        missing(monkeypatch, "ffmpeg", "ffprobe")

        with pytest.raises(SystemExit) as exc:
            run_main(monkeypatch, flag)

        assert exc.value.code == 0
        assert "not found" not in capsys.readouterr().err

    def test_list_sources_skips_the_check(self, monkeypatch, capsys):
        missing(monkeypatch, "ffmpeg", "ffprobe")

        run_main(monkeypatch, "--list-sources")

        captured = capsys.readouterr()
        assert "Metadata priority:" in captured.out
        assert "not found" not in captured.err
