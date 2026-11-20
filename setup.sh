#!/usr/bin/env bash
# Set up the Python environment for the vision code (macOS and Linux).
#
# Run from the project folder:
#     bash setup.sh
#
# Options:
#     --skip-tests    do not run the test suite at the end (saves about 30 seconds)
#
# What it does:
#     1. Finds Python 3.10 or newer.
#     2. Makes a private environment in the .venv folder.
#     3. Installs the packages in requirements.txt (and pytest).
#     4. Checks that the packages load, runs the tests, and looks for cameras.
# It is safe to run again. It never changes anything outside this folder.

set -euo pipefail
cd "$(dirname "$0")"

SKIP_TESTS=0
for arg in "$@"; do
    case "$arg" in
        --skip-tests) SKIP_TESTS=1 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

step() { printf '\n==> %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

# 1. Find Python 3.10 or newer.
step "Looking for Python 3.10 or newer"
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    fail "Python 3.10 or newer was not found.
Install it with Homebrew:  brew install python@3.13
(no Homebrew? download Python from https://www.python.org/downloads/)
Then open a new Terminal window and run this script again."
fi
echo "Found $("$PYTHON" --version)"

# 2. Make the .venv folder.
step "Making the .venv environment"
if [ -x .venv/bin/python ]; then
    echo ".venv already exists, reusing it"
else
    "$PYTHON" -m venv .venv || fail "Could not make .venv"
fi
VENV_PYTHON="$PWD/.venv/bin/python"

# 3. Install the packages.
step "Installing packages (needs internet, about 1 minute)"
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -r requirements.txt pytest \
    || fail "pip could not install the packages. Check your internet and try again."

# 4. Check the packages load.
step "Checking the packages"
"$VENV_PYTHON" -c "import cv2, numpy; print('OpenCV', cv2.__version__, '| NumPy', numpy.__version__)" \
    || fail "OpenCV or NumPy did not load"

if [ "$SKIP_TESTS" -eq 0 ]; then
    step "Running the tests (about 30 seconds)"
    "$VENV_PYTHON" -m pytest tests -q || fail "Some tests failed. Copy the text above and ask the team."
fi

step "Looking for cameras (not an error if none is found)"
"$VENV_PYTHON" - <<'EOF' || true
import cv2
found = []
for index in range(3):
    cap = cv2.VideoCapture(index)
    if cap.isOpened():
        found.append(index)
    cap.release()
print("Camera index found:", found if found else "none (plug in a USB camera, or use the laptop camera)")
EOF

printf '\nSetup done.\n'
echo "Every new Terminal window, turn the environment on first:"
echo "    source .venv/bin/activate"
echo "Then run the vision code:"
echo "    python vision/tray_object_pipeline.py --camera-index 0"
echo "(macOS asks to let Terminal use the camera the first time. Click Allow.)"
