# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.metadata.lyrics``.

Kept so ``trackfetch.lyrics`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.lyrics`` returns the same object everywhere.
"""

import sys

from trackfetch.metadata.lyrics import *  # noqa: F401,F403

_real = sys.modules["trackfetch.metadata.lyrics"]
sys.modules["trackfetch.lyrics"] = _real
