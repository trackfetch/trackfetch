# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.audio.youtube``.

Kept so ``trackfetch.youtube`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.youtube`` returns the same object everywhere.
"""

import sys

from trackfetch.audio.youtube import *  # noqa: F401,F403

_real = sys.modules["trackfetch.audio.youtube"]
sys.modules["trackfetch.youtube"] = _real
