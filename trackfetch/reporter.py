# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.reporter``.

Kept so ``trackfetch.reporter`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.reporter`` returns the same object everywhere.
"""

import sys

from trackfetch.core.reporter import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.reporter"]
sys.modules["trackfetch.reporter"] = _real
