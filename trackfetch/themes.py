# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.ui.themes``.

Kept so ``trackfetch.themes`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.themes`` returns the same object everywhere.
"""

import sys

from trackfetch.ui.themes import *  # noqa: F401,F403

_real = sys.modules["trackfetch.ui.themes"]
sys.modules["trackfetch.themes"] = _real
