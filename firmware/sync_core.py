"""Copies the shared core (firmware/tray_cap_core) into each sketch's src/core folder.

The Arduino IDE only builds files inside the sketch folder, so every sketch needs its own
copy. Edit the core in tray_cap_core only, then run:  python firmware/sync_core.py
tests/test_core_copies.py checks that the copies are identical.
"""
import shutil
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent
CORE = FIRMWARE / "tray_cap_core"
SKETCHES = ["ESP32CamPipeline", "AMB82Pipeline"]
SKIP = ("pc_test", "__pycache__")


def core_files():
    for path in sorted(CORE.rglob("*")):
        relative = path.relative_to(CORE)
        if path.is_file() and not any(part in SKIP for part in relative.parts):
            yield relative


def sync():
    for sketch in SKETCHES:
        target = FIRMWARE / sketch / "src" / "core"
        if target.exists():
            shutil.rmtree(target)
        for relative in core_files():
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CORE / relative, target / relative)
        print(f"{sketch}: copied to {target.relative_to(FIRMWARE)}")


if __name__ == "__main__":
    sync()
