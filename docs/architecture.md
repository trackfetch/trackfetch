# Architecture

[![Architecture diagram of trackfetch/trackfetch](https://gitdiagram.com/trackfetch/trackfetch/diagram.png)](https://gitdiagram.com/trackfetch/trackfetch?utm_source=readme&utm_medium=picture)

TrackFetch used to be one `trackfetch.py` module. It is now a small package
with one responsibility per module. The public API is still available from
`import trackfetch`, so the console script and existing integrations keep
working.

## Module map

The package is organized in layers. Old top-level module paths were removed;
import the focused module directly or use the public facade (`import
trackfetch`), which re-exports the documented names.

```
trackfetch/
├── __init__.py          Public facade and re-exports
├── __main__.py          python -m trackfetch
├── _lazy.py             Lazy name/submodule maps for the facade
├── cli.py               Parser composition, help setup and entry point
├── cli_options.py       Argument groups and option definitions
├── errors.py            TrackFetchError hierarchy (config, tagging, cover)
├── enums.py             AudioFormat / MusicSource str-enums
├── protocols.py         AudioSource / Tagger runtime-checkable protocols
├── scoring.py           Frozen dataclasses for candidate scoring
├── audio/
│   ├── youtube/         Search, scoring, age probe, download
│   └── soundcloud/      Fallback search, matching, selection, download
├── config_pkg/
│   ├── constants.py     Defaults, provider tables, regexes
│   ├── model.py         SourceConfig and source-list formatting
│   ├── validate.py      Source-name/boolean/interval validation
│   ├── loader.py        Settings and CLI value resolution
│   ├── builder.py       build_source_config
│   ├── config.py        Re-export facade for the modules above
│   └── settings.py      Config-file discovery and CLI/config precedence
├── core/
│   ├── context.py       RunContext: immutable per-run settings
│   ├── result.py        Result: success/skip/fail outcome of one song
│   ├── reporter.py      Exact per-song progress lines
│   ├── inputs.py        Input discovery, deduplication and output setup
│   ├── runner.py        run_songs: download loop, done/failed logs, summary
│   ├── dependencies.py  Startup check for ffmpeg and ffprobe
│   ├── sources.py       AudioSource implementations and registry
│   ├── pipeline.py      One-song orchestration
│   ├── runtime.py       Health tracking, rate limiter, cache, HTTP session
│   ├── matching.py      Normalization, similarity and candidate scoring
│   ├── images.py        Cover detection, download, Pillow normalization
│   └── files.py         Filenames, song parsing, done/failed logs
├── metadata/
│   └── lyrics.py        LRCLIB lookup, LRC parsing and sidecar writing
├── tagging/
│   ├── __init__.py      get_tagger factory and legacy add_metadata
│   ├── mp3.py           ID3 writer
│   ├── m4a.py           MP4 atom writer
│   └── opus.py          Vorbis-comment writer
├── ui/
│   ├── colors.py        Theme selection and ANSI rendering
│   ├── palettes.py      Built-in color palettes
│   ├── themes.py        Custom themes.ini discovery and parsing
│   └── helpfmt.py       Custom help formatter and epilog styling
├── providers/
│   ├── spotify.py       Optional Spotify provider
│   ├── itunes.py        iTunes Search API
│   ├── deezer.py        Deezer Search API
│   ├── musicbrainz.py   MusicBrainz + Cover Art Archive
│   ├── vocadb.py        VocaDB
│   ├── search.py        Shared query relaxation and candidate deduplication
│   ├── duration.py      Millisecond/second duration normalization
│   ├── registry.py      name -> provider function
│   └── resolver.py      Priority, cooldowns, cache-aware resolution
└── (no top-level compatibility shims)
```

## Dependency direction

Dependencies point in one direction:

```mermaid
flowchart TD
    subgraph Foundation
        constants[constants]
        errors[errors]
        matching[matching]
        colors[colors]
    end

    subgraph Configuration
        config[config]
        settings[settings]
        runtime[runtime]
        themes[themes]
    end

    subgraph Sources
        providers["providers/*"]
        youtube[youtube]
        images[images]
        lyrics[lyrics]
        tags[tags]
        files[files]
    end

    pipeline[pipeline]
    cli[cli]

    constants --> config
    errors --> config
    matching --> config
    constants --> settings
    config --> settings
    constants --> runtime
    errors --> runtime
    matching --> runtime
    colors --> themes
    constants --> themes
    settings --> themes

    config --> providers
    errors --> providers
    matching --> providers
    runtime --> providers
    constants --> youtube
    matching --> youtube
    colors --> youtube
    constants --> soundcloud
    errors --> soundcloud
    matching --> soundcloud
    colors --> soundcloud
    constants --> images
    colors --> images
    youtube --> images
    constants --> lyrics
    errors --> lyrics
    matching --> lyrics
    constants --> tags
    images --> tags
    lyrics --> tags
    constants --> files

    config --> pipeline
    colors --> pipeline
    files --> pipeline
    images --> pipeline
    lyrics --> pipeline
    providers --> pipeline
    tags --> pipeline
    youtube --> pipeline
    soundcloud --> pipeline

    colors --> cli
    themes --> cli
    config --> cli
    settings --> cli
    runtime --> cli
    files --> cli
    pipeline --> cli
```

This keeps the network providers independent from the CLI and makes each
piece testable on its own. `providers/registry.py` is the only place that
knows which providers exist; adding a provider means adding one module and
one registry entry.

Dependencies never point "up" the layers: `audio/`, `metadata/`, `providers/`
and `ui/` do not import from `core/`, and only `core/runner.py` and the
facade are allowed to touch `cli.py` territory (and even they do not — the
runner receives `process_song` as a parameter).

## Design rules

- **One run, one `MetadataRuntime`.** It owns the HTTP session, rate
  limiter, provider health, cache and Spotify client. Providers receive it
  instead of creating module-level clients. The per-run choices (format,
  quality, thresholds, runtime) travel in a frozen `RunContext`; the outcome
  of one song is a frozen `Result`.
- **Errors are typed.** Modules raise `ConfigError`, `TaggingError`,
  `CoverError` or `ProviderError` from `trackfetch/errors.py`; there are no
  bare `except Exception` handlers.
- **Providers return candidates; the resolver decides.** Provider functions
  only translate an API response into the common metadata dict. Thresholds,
  priority, cooldowns and caching live in `providers/resolver.py`.
- **The pipeline is the only place that knows the full download order.**
  Resolve metadata → pick a filename → try the configured music providers in
  priority order → download audio → download cover → embed tags and lyrics →
  move the finished file. With the default `youtube,soundcloud` priority,
  SoundCloud runs once when YouTube fails in the way the trigger allows. With
  `soundcloud,youtube`, SoundCloud is searched first and YouTube is the
  fallback.
- **`audio/soundcloud/` is pure matching plus two yt-dlp calls.** It never
  downloads audio; it returns a ranked, filtered candidate list and the
  pipeline downloads at most one URL. This keeps the scoring testable with
  plain dictionaries and keeps the download order in the pipeline.
- **The CLI never implements domain logic.** It parses arguments, builds a
  `SourceConfig`, creates the runtime and hands the song list to
  `core/runner.run_songs`, which owns the loop, the done/failed logs and the
  summary. Parser options live in `cli_options.py`; `cli.py` composes them.
- **Public names stay re-exported from `trackfetch/__init__.py`.** Tests and
  external code can keep using `trackfetch.normalize(...)`, while new code
  can import from the focused module directly.

## Adding a metadata provider

1. Create `trackfetch/providers/<name>.py` with a function that accepts
   `(runtime, artist, title, config)` and returns a list of candidate dicts.
2. Register it in `trackfetch/providers/registry.py`.
3. Add the provider to `METADATA_PROVIDERS`, `PROVIDER_DEFAULTS` and
   `PROVIDER_OPTIONS` in `trackfetch/config_pkg/constants.py`.
4. Re-export the provider function from `trackfetch/__init__.py` if it
   should be part of the public API.
