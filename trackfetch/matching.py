# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.matching``.

Kept so ``trackfetch.matching`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.matching`` returns the same object everywhere.
"""

import sys

from trackfetch.core.matching import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.matching"]
sys.modules["trackfetch.matching"] = _real
