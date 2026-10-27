"""Ermöglicht ``python -m sdcard_sync``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
