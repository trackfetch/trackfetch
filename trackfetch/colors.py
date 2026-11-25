# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.ui.colors``.

Kept so ``trackfetch.colors`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.colors`` returns the same object everywhere.
"""

import sys

from trackfetch.ui.colors import *  # noqa: F401,F403

_real = sys.modules["trackfetch.ui.colors"]
sys.modules["trackfetch.colors"] = _real
