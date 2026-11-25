# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.config_pkg.config``.

Kept so ``trackfetch.config`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.config`` returns the same object everywhere.
"""

import sys

from trackfetch.config_pkg.config import *  # noqa: F401,F403

_real = sys.modules["trackfetch.config_pkg.config"]
sys.modules["trackfetch.config"] = _real
