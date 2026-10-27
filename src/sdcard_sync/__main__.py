# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
"""Ermöglicht ``python -m sdcard_sync``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
