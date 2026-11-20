"""Checks that each sketch's src/core is an exact copy of firmware/tray_cap_core.

If this fails, run:  python firmware/sync_core.py
"""
import sys
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent.parent / "firmware"
sys.path.insert(0, str(FIRMWARE))

import sync_core  # noqa: E402


def test_sketch_copies_match_the_shared_core():
    for sketch in sync_core.SKETCHES:
        target = FIRMWARE / sketch / "src" / "core"
        for relative in sync_core.core_files():
            copy = target / relative
            assert copy.exists(), f"{sketch}: {relative} is missing. Run python firmware/sync_core.py"
            assert copy.read_bytes() == (sync_core.CORE / relative).read_bytes(), \
                f"{sketch}: {relative} differs. Run python firmware/sync_core.py"
