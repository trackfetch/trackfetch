# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.context``.

Kept so ``trackfetch.context`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.context`` returns the same object everywhere.
"""

import sys

from trackfetch.core.context import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.context"]
sys.modules["trackfetch.context"] = _real
