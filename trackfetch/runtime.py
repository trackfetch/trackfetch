# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.runtime``.

Kept so ``trackfetch.runtime`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.runtime`` returns the same object everywhere.
"""

import sys

from trackfetch.core.runtime import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.runtime"]
sys.modules["trackfetch.runtime"] = _real
