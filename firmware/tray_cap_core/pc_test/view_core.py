"""See inside the board code: run the C++ core (the code the AMB82 runs) on the PC,
with the same 6 windows as the Python program.

The C++ core is built into a small library (tc_core.dll) with g++ the first time.
Each frame is shrunk to fit 640 x 360 (the board's picture size) before the core sees it.

Examples (run from the repo root):
    python firmware/tray_cap_core/pc_test/view_core.py --url rtsp://192.168.0.25:554
    python firmware/tray_cap_core/pc_test/view_core.py --camera-index 0
    python firmware/tray_cap_core/pc_test/view_core.py --image picture.jpg
    python firmware/tray_cap_core/pc_test/view_core.py --video recording.mp4

Keys: q or Esc quits, r forgets the locked tray.
The JSON line and the "# debug:" line are printed for every frame.
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT))

from vision.camera import open_capture  # noqa: E402  (must load before cv2: it sets FFmpeg options)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

CORE = HERE.parent
LIBRARY = HERE / "tc_core.dll"
SOURCES = ["tc_image.cpp", "tc_tray.cpp", "tc_caps.cpp", "tc_pipeline.cpp", "tc_jpeg.cpp"]
MAX_W, MAX_H = 640, 360  # the board's picture size (MAX_W, MAX_H in tc_types.h)

WINDOWS = [
    "Camera / tray localization",
    "Tray threshold",
    "Tray mask",
    "Image restricted to tray",
    "Rectified tray / detected objects",
    "Colored-object mask",
]
CYAN, GREEN, YELLOW = (255, 255, 0), (0, 255, 0), (0, 255, 255)  # BGR
MASK_COLORS = {"red": (40, 40, 255), "blue": (255, 100, 60), "purple": (220, 80, 200)}  # BGR


def build_library():
    """Build tc_core.dll from the core sources when it is missing or older than them.

    Returns:
        Path of the library.

    Raises:
        SystemExit: If g++ is missing or the build fails.
    """
    sources = [CORE / s for s in SOURCES] + [HERE / "tc_capi.cpp", CORE / "third_party" / "tjpgd" / "tjpgd.c"]
    headers = list(CORE.glob("*.h"))
    newest = max(p.stat().st_mtime for p in sources + headers)
    if LIBRARY.exists() and LIBRARY.stat().st_mtime >= newest:
        return LIBRARY
    gcc, gxx = shutil.which("gcc"), shutil.which("g++")
    if gcc is None or gxx is None:
        raise SystemExit("g++ is not installed. Install MSYS2 (ucrt64) and add its bin folder to PATH.")
    print("# building", LIBRARY.name, file=sys.stderr)
    tjpgd_object = HERE / "tjpgd_view.o"
    steps = [
        [gcc, "-O2", "-c", "-o", str(tjpgd_object), str(sources[-1])],
        [gxx, "-std=c++17", "-O2", "-shared", "-static", "-static-libgcc", "-static-libstdc++",
         "-o", str(LIBRARY)] + [str(p) for p in sources[:-1]] + [str(tjpgd_object)],
    ]
    for step in steps:
        done = subprocess.run(step, capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit("build failed:\n" + done.stderr)
    tjpgd_object.unlink(missing_ok=True)
    return LIBRARY


class Core:
    """The C++ pipeline, through tc_capi.cpp.

    Attributes:
        width: Picture width the core was made for.
        height: Picture height the core was made for.
    """

    def __init__(self, width, height, min_side, region=None):
        self.lib = ctypes.CDLL(str(build_library()))
        lib = self.lib
        lib.tc_new.restype = ctypes.c_void_p
        lib.tc_new.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.tc_free.argtypes = [ctypes.c_void_p]
        lib.tc_set_region.argtypes = [ctypes.c_void_p] + [ctypes.c_float] * 4
        lib.tc_reset_tray.argtypes = [ctypes.c_void_p]
        lib.tc_process.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.tc_outline.restype = ctypes.c_int
        lib.tc_outline.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.tc_dark.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.tc_straight_size.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        lib.tc_straight.argtypes = [ctypes.c_void_p] * 5
        self.handle = lib.tc_new(width, height, min_side)
        if not self.handle:
            raise SystemExit(f"the core cannot take {width} x {height} (biggest is {MAX_W} x {MAX_H})")
        if region is not None:
            lib.tc_set_region(self.handle, *region)
        self.width, self.height = width, height
        self.json = ctypes.create_string_buffer(4096)
        self.debug = ctypes.create_string_buffer(512)

    def process(self, rgb, now_ms, frame_number):
        """Run one frame. Returns (json_line, debug_line)."""
        rgb = np.ascontiguousarray(rgb)
        self.lib.tc_process(self.handle, rgb.ctypes.data, now_ms, frame_number,
                            self.json, len(self.json), self.debug, len(self.debug))
        return self.json.value.decode(), self.debug.value.decode()

    def outline(self):
        xy = np.zeros(8, np.float32)
        if not self.lib.tc_outline(self.handle, xy.ctypes.data):
            return None
        return xy.reshape(4, 2)

    def dark(self):
        out = np.zeros((self.height, self.width), np.uint8)
        self.lib.tc_dark(self.handle, out.ctypes.data)
        return out

    def straight(self):
        """Returns (hsv, {color: mask}) of the straightened tray, or (None, None)."""
        w, h = ctypes.c_int(), ctypes.c_int()
        self.lib.tc_straight_size(self.handle, ctypes.byref(w), ctypes.byref(h))
        if w.value <= 0 or h.value <= 0:
            return None, None
        hsv = np.zeros((h.value, w.value, 3), np.uint8)
        masks = {c: np.zeros((h.value, w.value), np.uint8) for c in ("red", "blue", "purple")}
        self.lib.tc_straight(self.handle, hsv.ctypes.data, masks["red"].ctypes.data,
                             masks["blue"].ctypes.data, masks["purple"].ctypes.data)
        return hsv, masks

    def reset_tray(self):
        self.lib.tc_reset_tray(self.handle)


def fit_to_board(frame):
    """Shrink a BGR frame to fit MAX_W x MAX_H, keeping its shape."""
    h, w = frame.shape[:2]
    scale = min(MAX_W / w, MAX_H / h, 1.0)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return frame


def tray_point(corners, u, v):
    """Place a tray fraction (u, v) in the camera picture, as the board overlay does."""
    top = corners[0] + (corners[1] - corners[0]) * u
    bottom = corners[3] + (corners[2] - corners[3]) * u
    point = top + (bottom - top) * v
    return int(point[0]), int(point[1])


def make_views(frame, core, result):
    """Build the 6 pictures from the core's state after a frame."""
    corners = core.outline()
    state = result["tray"]
    caps = result["caps"]

    overview = frame.copy()
    tray_mask = np.zeros(frame.shape[:2], np.uint8)
    if corners is not None:
        color = CYAN if state == "locked" else GREEN
        cv2.polylines(overview, [corners.astype(np.int32)], True, color, 2)
        cv2.fillPoly(tray_mask, [corners.astype(np.int32)], 255)
        for cap in caps:
            x, y = tray_point(corners, cap["u"], cap["v"])
            cv2.drawMarker(overview, (x, y), YELLOW, cv2.MARKER_CROSS, 14, 2)
            cv2.putText(overview, f'{cap["color"]} {cap["u"]:.2f} {cap["v"]:.2f}', (x + 8, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, YELLOW, 1, cv2.LINE_AA)
    label = {"locked": "TRAY LOCKED", "finding": "FINDING TRAY", "settling": "LOCALIZE TRAY",
             "not_found": "NO TRAY"}.get(state, state)
    cv2.putText(overview, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, CYAN if state == "locked" else GREEN, 2)

    tray_only = cv2.bitwise_and(frame, frame, mask=tray_mask)

    hsv, masks = core.straight()
    if hsv is None:
        detection = np.zeros((180, 320, 3), np.uint8)
        color_mask = np.zeros((180, 320, 3), np.uint8)
    else:
        detection = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        for cap in caps:
            x, y, w, h = cap["box"]
            cv2.rectangle(detection, (x, y), (x + w - 1, y + h - 1), YELLOW, 1)
            cv2.putText(detection, cap["color"], (x, max(10, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, YELLOW, 1)
        color_mask = np.zeros(hsv.shape, np.uint8)
        for name, mask in masks.items():
            color_mask[mask > 0] = MASK_COLORS[name]
        # Small pictures are hard to see: show the tray views at least 360 px wide.
        scale = max(1, 360 // detection.shape[1])
        if scale > 1:
            size = (detection.shape[1] * scale, detection.shape[0] * scale)
            detection = cv2.resize(detection, size, interpolation=cv2.INTER_NEAREST)
            color_mask = cv2.resize(color_mask, size, interpolation=cv2.INTER_NEAREST)

    return [overview, core.dark(), tray_mask, tray_only, detection, color_mask]


def frames(args):
    """Yield BGR frames from the chosen source. A still picture repeats until you quit."""
    if args.image:
        picture = cv2.imread(args.image)
        if picture is None:
            raise SystemExit(f"cannot read {args.image}")
        while True:
            yield picture
            time.sleep(0.1)
    source = args.video if args.video else (args.camera_index if args.camera_index is not None else args.url)
    if args.video:
        video = cv2.VideoCapture(args.video)
        if not video.isOpened():
            raise SystemExit(f"cannot open {args.video}")
    else:
        video = open_capture(source, args.transport)
    while True:
        ok, frame = video.read()
        if not ok:
            print("# no more frames", file=sys.stderr)
            return
        yield frame


def tray_region(text):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("use four numbers: left,top,right,bottom")
    return parts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", default="rtsp://192.168.0.25:554", help="RTSP stream (default: the AMB82)")
    source.add_argument("--camera-index", type=int, help="USB camera number")
    source.add_argument("--image", help="a still picture (repeated)")
    source.add_argument("--video", help="a video file")
    parser.add_argument("--transport", choices=("auto", "tcp", "udp"), default="auto")
    parser.add_argument("--tray-region", type=tray_region, default=None,
                        help="left,top,right,bottom fractions, like USE_TRAY_REGION on the board")
    parser.add_argument("--min-side", type=int, default=8,
                        help="smallest cap side in pixels (the board uses 8 today)")
    args = parser.parse_args()

    core = None
    start = time.monotonic()
    for name in WINDOWS:
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    for frame_number, frame in enumerate(frames(args), start=1):
        frame = fit_to_board(frame)
        if core is None:
            core = Core(frame.shape[1], frame.shape[0], args.min_side, args.tray_region)
            print(f"# core running on {core.width} x {core.height}", file=sys.stderr)
        now_ms = int((time.monotonic() - start) * 1000)
        json_line, debug_line = core.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), now_ms, frame_number)
        print(json_line, flush=True)
        print(debug_line, file=sys.stderr, flush=True)
        for name, view in zip(WINDOWS, make_views(frame, core, json.loads(json_line))):
            cv2.imshow(name, view)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            core.reset_tray()
            print("# tray forgotten, searching again", file=sys.stderr)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
