#!/usr/bin/env python3
"""Repository entry point for non-patient phantom CT water replacement."""

from __future__ import annotations

from pathlib import Path
import sys


PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.replace_ct_layer_with_water import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
