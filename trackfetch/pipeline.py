# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.pipeline``.

Kept so ``trackfetch.pipeline`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.pipeline`` returns the same object everywhere.
"""

import sys

from trackfetch.core.pipeline import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.pipeline"]
sys.modules["trackfetch.pipeline"] = _real
