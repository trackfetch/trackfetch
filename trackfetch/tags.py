# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.tagging``.

Kept so ``trackfetch.tags`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.tags`` returns the same object everywhere.
"""

import sys

from trackfetch.tagging import *  # noqa: F401,F403

_real = sys.modules["trackfetch.tagging"]
sys.modules["trackfetch.tags"] = _real
