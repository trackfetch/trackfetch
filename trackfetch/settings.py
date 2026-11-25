# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.config_pkg.settings``.

Kept so ``trackfetch.settings`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.settings`` returns the same object everywhere.
"""

import sys

from trackfetch.config_pkg.settings import *  # noqa: F401,F403

_real = sys.modules["trackfetch.config_pkg.settings"]
sys.modules["trackfetch.settings"] = _real
