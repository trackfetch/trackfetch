# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim: the module moved to ``trackfetch.core.files``.

Kept so ``trackfetch.files`` keeps working for the public facade and
tests. The real module is registered in ``sys.modules`` under the old
name, so ``import trackfetch.files`` returns the same object everywhere.
"""

import sys

from trackfetch.core.files import *  # noqa: F401,F403

_real = sys.modules["trackfetch.core.files"]
sys.modules["trackfetch.files"] = _real
