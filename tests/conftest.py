import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trackfetch.ui import colors  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def reset_color_state():
    """Keep color globals and custom themes from leaking between tests."""
    themes = dict(colors.THEMES)
    custom = set(colors._custom_themes)
    mode = colors.get_color_mode()
    theme = colors.get_theme()
    windows_ready = colors._windows_ansi_ready

    yield

    colors.THEMES.clear()
    colors.THEMES.update(themes)
    colors._custom_themes.clear()
    colors._custom_themes.update(custom)
    colors.set_color_mode(mode)
    colors.set_theme(theme)
    colors._windows_ansi_ready = windows_ready


@pytest.fixture(autouse=True)
def assume_ffmpeg_available(monkeypatch):
    """Keep the suite independent of the host's FFmpeg installation."""
    from trackfetch.core import dependencies

    real_which = dependencies.shutil.which

    def fake_which(command):
        return real_which(command) or f"/usr/local/bin/{command}"

    monkeypatch.setattr(dependencies.shutil, "which", fake_which)


def make_track(
    name="Song",
    artists=("Artist",),
    album="Album",
    album_artists=None,
    track_number=3,
    release_date="2001-03-12",
    images=({"url": "https://img/640.jpg"},),
    duration_ms=None,
):
    """Minimal Spotify track object with the fields trackfetch reads."""
    album_artists = artists if album_artists is None else album_artists
    return {
        "name": name,
        "artists": [{"name": a} for a in artists],
        "track_number": track_number,
        "duration_ms": duration_ms,
        "album": {
            "name": album,
            "artists": [{"name": a} for a in album_artists],
            "release_date": release_date,
            "images": list(images),
        },
    }


class FakeSpotify:
    """Returns queued responses from search() and records the queries."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.queries = []

    def search(self, q, type, limit):
        self.queries.append(q)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"tracks": {"items": response}}


@pytest.fixture
def metadata():
    return {
        "artist": "Daft Punk",
        "title": "One More Time",
        "album": "Discovery",
        "album_artist": "Daft Punk",
        "track_number": 1,
        "release_date": "2001-03-12",
        "cover_url": "https://img/cover.jpg",
    }


@pytest.fixture
def make_ctx():
    """Build a RunContext with test-friendly defaults."""
    import trackfetch
    from trackfetch.config_pkg.constants import DEFAULT_AUDIO_QUALITY

    def build(**overrides):
        values = {
            "output": Path.cwd(),
            "title_only": False,
            "audio_format": "mp3",
            "audio_quality": DEFAULT_AUDIO_QUALITY,
            "source_config": None,
            "runtime": None,
            "lyrics_type": None,
            "input_artist": "",
            "input_title": "",
        }
        values.update(overrides)

        if values["source_config"] is None:
            values["source_config"] = trackfetch.build_source_config(None, {})

        if values["lyrics_type"] is None:
            values["lyrics_type"] = values["source_config"].lyrics_type

        return trackfetch.RunContext(**values)

    return build
