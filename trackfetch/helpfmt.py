# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.ui.helpfmt``.

Kept so ``trackfetch.helpfmt`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.helpfmt`` returns the same object everywhere.
"""

import sys

from trackfetch.ui.helpfmt import *  # noqa: F401,F403

_real = sys.modules["trackfetch.ui.helpfmt"]
sys.modules["trackfetch.helpfmt"] = _real
