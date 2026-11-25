# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.config_pkg.constants``.

Kept so ``trackfetch.constants`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.constants`` returns the same object everywhere.
"""

import sys

from trackfetch.config_pkg.constants import *  # noqa: F401,F403

_real = sys.modules["trackfetch.config_pkg.constants"]
sys.modules["trackfetch.constants"] = _real
