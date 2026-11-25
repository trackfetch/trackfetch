# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.tags``.

Kept so ``trackfetch.tags`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.tags`` returns the same object everywhere.
"""

import sys

from trackfetch.core.tags import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.tags"]
sys.modules["trackfetch.tags"] = _real
