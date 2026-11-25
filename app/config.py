"""Backwards-compatible alias for :mod:`app.configs`.

All settings now live in ``app/configs.py``.  This module is kept so older
imports (and the existing test-suite) keep working.
"""

from app.configs import *
