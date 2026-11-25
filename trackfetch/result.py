# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.result``.

Kept so ``trackfetch.result`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.result`` returns the same object everywhere.
"""

import sys

from trackfetch.core.result import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.result"]
sys.modules["trackfetch.result"] = _real
