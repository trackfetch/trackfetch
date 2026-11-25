# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.images``.

Kept so ``trackfetch.images`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.images`` returns the same object everywhere.
"""

import sys

from trackfetch.core.images import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.images"]
sys.modules["trackfetch.images"] = _real
