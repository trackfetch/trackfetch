# SPDX-License-Identifier: GPL-3.0-or-later
"""The song download loop: progress display, done/failed logs, summary."""

import time

from ..core.files import append_line
from ..ui import colors


def format_summary(label_text, value, role):
    """Color a summary label and value, muting zero counts."""
    value_style = role if value else "muted"
    return (
        f"{colors.paint(label_text, role, 'bold')} "
        f"{colors.paint(value, value_style)}"
    )


def run_songs(songs, done, done_file, failed_file, args, source_config,
              runtime, process_song):
    """Download every song, keeping the done.txt/failed.txt logs in sync.

    ``process_song`` is passed in so a plain ``-h`` or ``--list-sources``
    run never pays for importing the pipeline stack.
    """
    success = 0
    skipped = 0
    failed = 0

    for number, (artist, title) in enumerate(
        songs,
        start=1,
    ):
        song_key = f"{artist} - {title}"

        print()
        print(colors.frame("=" * 60))
        print(colors.progress(f"[{number}/{len(songs)}]"))
        print(colors.paint(song_key, "text", "bold"))

        if song_key in done:
            print(colors.skip("SKIP: already completed"))
            skipped += 1
            continue

        ok, reason = process_song(
            artist,
            title,
            args.output,
            args.title_only,
            args.format,
            args.audio_quality,
            source_config=source_config,
            runtime=runtime,
        )

        if ok:
            if not args.no_logs:
                append_line(
                    done_file,
                    song_key,
                )

            done.add(song_key)

            if reason == "exists":
                skipped += 1

            else:
                success += 1

        else:
            if not args.no_logs:
                append_line(
                    failed_file,
                    f"{song_key} | {reason}",
                )

            failed += 1

        if number < len(songs):
            time.sleep(args.delay)

    print()
    print(colors.frame("=" * 60))
    print(colors.heading("FINISHED"))
    print(format_summary("SUCCESS:", success, "success"))
    print(format_summary("SKIPPED:", skipped, "skip"))
    print(format_summary("FAILED:", failed, "error"))

    if not args.no_logs:
        print(f"{colors.label('DONE FILE:')} {colors.muted(done_file)}")
        print(f"{colors.label('FAILED FILE:')} {colors.muted(failed_file)}")
