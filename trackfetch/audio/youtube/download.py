# SPDX-License-Identifier: GPL-3.0-or-later
"""yt-dlp download execution and progress forwarding."""

import subprocess
import sys


def run_streaming(command, limit=8000):
    """Run a command, echo stderr live and keep its tail.

    yt-dlp writes both the progress bar and errors to stderr. Hiding it would
    hide progress on a long download, so each line is forwarded as it arrives
    and only the tail is kept for error classification.
    """
    process = subprocess.Popen(
        command,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    captured = []

    try:
        for line in process.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()
            captured.append(line)

        returncode = process.wait()

    except BaseException:
        process.kill()
        process.wait()
        raise

    finally:
        process.stderr.close()

    return returncode, "".join(captured)[-limit:].strip()


__all__ = ["run_streaming"]
