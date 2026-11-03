"""Locate a moving black tray, rectify it, and find colored objects on it.

Runs on the PC. The tray and objects must lie on the same flat work surface.
Reported coordinates are normalized to the rectified tray; robot-base
coordinates require a later camera-to-robot calibration. 
"""

import argparse
import os
import sys
import time


def _configure_ffmpeg_from_args():
    """Set FFmpeg options before importing OpenCV."""
    url = "rtsp://192.168.0.25:554"
    transport = "auto"
    args = sys.argv[1:]
    for i, arg in enumerate(args[:-1]):
        if arg == "--url":
            url = args[i + 1]
        elif arg == "--transport":
            transport = args[i + 1]

    if url.lower().startswith(("http://", "https://")):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTION"] = "timeout;7000000"
    elif transport == "udp":
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;udp|timeout;7000000"
        )
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_flags;prefer_tcp|timeout;7000000"
        )


_configure_ffmpeg_from_args()

import cv2
import numpy as np


def order_quad(points):
    """Order four image points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    ordered = pts[np.argsort(angles)]
    first = int(np.argmin(ordered.sum(axis=1)))
    return np.roll(ordered, -first, axis=0).astype(np.float32)


def tray_quad(frame, min_hue, max_hue, min_saturation, min_value,
              max_saturation, max_value, min_area_ratio, close_kernel):
    """Find a dark, low-saturation tray and return its four-corner outline."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    threshold = cv2.inRange(
        hsv,
        np.array([min_hue, min_saturation, min_value], dtype=np.uint8),
        np.array([max_hue, max_saturation, max_value], dtype=np.uint8),
    )
    k = max(3, close_kernel | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    threshold = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(
        threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    frame_area = float(frame.shape[0] * frame.shape[1])
    height, width = frame.shape[:2]
    border = max(4, int(min(height, width) * 0.008))
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area / frame_area < min_area_ratio:
            continue

        x, y, box_width, box_height = cv2.boundingRect(contour)
        # Bright windows and monitor areas often touch the image border. A
        # tray clipped by the frame is also unsafe to rectify, so reject it.
        if (x <= border or y <= border or
                x + box_width >= width - border or
                y + box_height >= height - border):
            continue

        hull = cv2.convexHull(contour)
        rect = cv2.minAreaRect(hull)
        rect_width, rect_height = rect[1]
        short_side = min(rect_width, rect_height)
        long_side = max(rect_width, rect_height)
        if short_side < 2:
            continue
        aspect_ratio = long_side / short_side
        rectangularity = area / (rect_width * rect_height)
        # A low camera angle can make a rectangular tray look very shallow.
        if not 1.2 <= aspect_ratio <= 8.0 or rectangularity < 0.48:
            continue

        perimeter = cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(hull, 0.04 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = order_quad(approx)
        elif rectangularity >= 0.58:
            # Foam texture can make the outline irregular; use the rotated
            # rectangle only when the candidate itself is fairly rectangular.
            quad = order_quad(cv2.boxPoints(rect))
        else:
            continue

        center_y = (y + box_height * 0.5) / height
        score = (area / frame_area) * rectangularity * (0.8 + 0.2 * center_y)
        candidates.append((score, quad))

    if not candidates:
        return None, threshold
    return max(candidates, key=lambda candidate: candidate[0])[1], threshold


class TrayQuadTracker:
    """Smooth frame noise while requiring confirmation for abrupt jumps."""

    def __init__(self, alpha=0.28, hold_frames=8, jump_confirm_frames=3):
        self.alpha = alpha
        self.hold_frames = hold_frames
        self.jump_confirm_frames = jump_confirm_frames
        self.current = None
        self.missed = 0
        self.pending = None
        self.pending_count = 0

    def update(self, candidate, frame_shape):
        if candidate is None:
            self.missed += 1
            if self.current is not None and self.missed <= self.hold_frames:
                return self.current.copy()
            self.current = None
            self.pending = None
            self.pending_count = 0
            return None

        candidate = order_quad(candidate)
        self.missed = 0
        if self.current is None:
            self.current = candidate
            return candidate.copy()

        height, width = frame_shape[:2]
        frame_diagonal = float(np.hypot(width, height))
        jump = float(np.mean(np.linalg.norm(candidate - self.current, axis=1)))
        if jump > frame_diagonal * 0.10:
            if self.pending is not None:
                pending_delta = float(
                    np.mean(np.linalg.norm(candidate - self.pending, axis=1))
                )
            else:
                pending_delta = float("inf")
            if pending_delta <= frame_diagonal * 0.035:
                self.pending = 0.5 * self.pending + 0.5 * candidate
                self.pending_count += 1
            else:
                self.pending = candidate.copy()
                self.pending_count = 1
            if self.pending_count < self.jump_confirm_frames:
                return self.current.copy()
            self.current = candidate
            self.pending = None
            self.pending_count = 0
            return self.current.copy()

        self.pending = None
        self.pending_count = 0
        self.current = (1.0 - self.alpha) * self.current + self.alpha * candidate
        return self.current.copy()


def _corner_distance(a, b):
    """Average distance between matching corners of two outlines, in pixels."""
    return float(np.mean(np.linalg.norm(a - b, axis=1)))


def _side_lengths(quad):
    return np.linalg.norm(quad - np.roll(quad, -1, axis=0), axis=1)


def tray_moved(locked, candidate, frame_shape, min_shift=0.05, size_tolerance=0.15):
    """True if `candidate` looks like the same tray, clearly somewhere else.

    Glare bends one side or corner, which changes the tray's shape. A moved
    tray keeps its shape (same side lengths) but shifts by at least
    `min_shift` of the image diagonal.

    Simple stand-in: Task 4's check_outline (same / moved / bent) in
    docs/task_delegation.md can replace this later.
    """
    diagonal = float(np.hypot(frame_shape[1], frame_shape[0]))
    if _corner_distance(locked, candidate) < min_shift * diagonal:
        return False
    ratios = _side_lengths(candidate) / np.maximum(_side_lengths(locked), 1.0)
    return bool(np.all(np.abs(ratios - 1.0) <= size_tolerance))


class TrayLock:
    """Freeze the tray outline once it has been steady, so glare can't move it.

    Not locked: the tracked outline is used, and once it stays within
    `steady_fraction` of the image diagonal for `lock_seconds`, it is locked.
    Locked: the locked outline is used every frame, even when the tray is
    hidden. It unlocks when a raw detection shows the same-shaped tray clearly
    moved, in the same new place, for `move_seconds`; or when unlock() is
    called (the 'r' key).
    """

    def __init__(self, lock_seconds=2.0, move_seconds=1.0, steady_fraction=0.015):
        self.lock_seconds = lock_seconds
        self.move_seconds = move_seconds
        self.steady_fraction = steady_fraction
        self.locked_quad = None
        self._anchor = None
        self._anchor_time = None
        self._moved_quad = None
        self._moved_since = None

    @property
    def locked(self):
        return self.locked_quad is not None

    def unlock(self):
        self.locked_quad = None
        self._anchor = self._anchor_time = None
        self._moved_quad = self._moved_since = None

    def seconds_to_lock(self, now):
        if self.locked or self._anchor_time is None:
            return None
        return max(0.0, self.lock_seconds - (now - self._anchor_time))

    def update(self, tracked_quad, detected_quad, frame_shape, now):
        """Return (outline to use, moved_quad). moved_quad is set on auto-unlock."""
        diagonal = float(np.hypot(frame_shape[1], frame_shape[0]))
        if not self.locked:
            if tracked_quad is None:
                self._anchor = self._anchor_time = None
                return None, None
            if (self._anchor is None or
                    _corner_distance(tracked_quad, self._anchor) > self.steady_fraction * diagonal):
                self._anchor, self._anchor_time = tracked_quad.copy(), now
            elif now - self._anchor_time >= self.lock_seconds:
                self.locked_quad = tracked_quad.copy()
            return tracked_quad, None

        # Locked: watch raw detections for a tray that really moved.
        if detected_quad is not None:
            candidate = order_quad(detected_quad)
            if tray_moved(self.locked_quad, candidate, frame_shape):
                same_spot = (self._moved_quad is not None and
                             _corner_distance(candidate, self._moved_quad) <= 0.02 * diagonal)
                if not same_spot:
                    self._moved_quad, self._moved_since = candidate, now
                elif now - self._moved_since >= self.move_seconds:
                    self.unlock()
                    return candidate, candidate
            else:
                self._moved_quad = self._moved_since = None
        return self.locked_quad.copy(), None


def rectify_tray(frame, quad):
    """Perspective-warp the detected tray to a top-down rectangular view."""
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    width = max(width, 2)
    height = max(height, 2)
    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(quad, target)
    return cv2.warpPerspective(frame, transform, (width, height)), transform


# Dark blue only. Glare on the dark tray reads as pale light blue (hue
# 94-104, saturation 76-132), so light blue can't be told apart from glare.
# Dark blue caps measured hue 101-115, saturation 140-255.
BLUE_MIN_HUE = 100
BLUE_MIN_SATURATION = 120

# Red's own saturation limit. The red object is a pale, pinkish red (hue 0-11,
# saturation 30-110). Red stops at hue 10, well clear of skin (hue 16-23).
RED_MIN_SATURATION = 50

# A cap pixel must be this much brighter than the tray's typical brightness.
# The camera's color balance drifts: the black tray has looked yellowish and,
# later, navy blue (as blue as the caps). Only brightness still told them apart.
TRAY_BRIGHTNESS_MARGIN = 25


def brightness_floor(hsv, min_value):
    """Return (tray brightness, brightness a cap pixel needs).

    The straightened view is mostly tray, so its median brightness is the
    tray's. The floor sits TRAY_BRIGHTNESS_MARGIN above it, never below
    min_value.
    """
    tray_brightness = int(np.median(hsv[..., 2]))
    return tray_brightness, min(255, max(min_value, tray_brightness + TRAY_BRIGHTNESS_MARGIN))


def color_masks(warped, min_saturation, min_value):
    """Return basic HSV masks for red, blue, and purple project objects."""
    hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
    smin = min_saturation
    _, vmin = brightness_floor(hsv, min_value)

    masks = {
        # Red sits at both ends of the hue scale, so it needs two ranges.
        "red": cv2.bitwise_or(
            cv2.inRange(
                hsv, np.array([0, RED_MIN_SATURATION, vmin], dtype=np.uint8),
                np.array([10, 255, 255], dtype=np.uint8),
            ),
            cv2.inRange(
                hsv, np.array([170, RED_MIN_SATURATION, vmin], dtype=np.uint8),
                np.array([179, 255, 255], dtype=np.uint8),
            ),
        ),
        "blue": cv2.inRange(
            hsv, np.array([BLUE_MIN_HUE, BLUE_MIN_SATURATION, vmin], dtype=np.uint8),
            np.array([124, 255, 255], dtype=np.uint8),
        ),
        "purple": cv2.inRange(
            hsv, np.array([125, smin, vmin], dtype=np.uint8),
            np.array([165, 255, 255], dtype=np.uint8),
        ),
    }

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for name, mask in masks.items():
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        masks[name] = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return masks


def find_objects(warped, masks, min_object_area_ratio, max_aspect_ratio=1.9):
    """Find compact colored objects and suppress duplicate color fragments."""
    h, w = warped.shape[:2]
    minimum_area = h * w * min_object_area_ratio
    objects = []
    for color, mask in masks.items():
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < minimum_area:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]
            x, y, box_w, box_h = cv2.boundingRect(contour)
            # Objects used in this project (caps and a ball) are compact.
            # Long strips of colored background in the camera view are not.
            if min(box_w, box_h) < 12:
                continue
            aspect = max(box_w, box_h) / float(min(box_w, box_h))
            if aspect > max_aspect_ratio:
                continue
            objects.append({
                "color": color,
                "cx": cx,
                "cy": cy,
                "u": cx / w,
                "v": cy / h,
                "box": (x, y, box_w, box_h),
                "area": area,
            })
    # One physical item can produce separate hue regions (especially a
    # ball under glare). Keep the largest candidate when boxes overlap.
    objects.sort(key=lambda obj: obj["area"], reverse=True)
    kept = []
    for obj in objects:
        x, y, box_w, box_h = obj["box"]
        duplicate = False
        for prior in kept:
            px, py, pw, ph = prior["box"]
            ix1, iy1 = max(x, px), max(y, py)
            ix2, iy2 = min(x + box_w, px + pw), min(y + box_h, py + ph)
            intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = box_w * box_h + pw * ph - intersection
            smaller_box_area = min(box_w * box_h, pw * ph)
            overlap_of_smaller = (
                intersection / float(smaller_box_area) if smaller_box_area else 0.0
            )
            # Small color patches inside a larger ball are color
            # variation or glare, not separate objects.
            if ((union and intersection / union >= 0.30) or
                    overlap_of_smaller >= 0.75):
                duplicate = True
                break
        if not duplicate:
            kept.append(obj)
    return kept


class ObjectTracker:
    """Steady object boxes across frames.

    Each frame is detected from scratch, so noise and glare make boxes jump
    or blink. This tracker matches each detection to the same-color object
    from earlier frames, shows an object only once it was seen in
    `min_hits` of the last `window` frames, and reports the median box and
    center of its recent detections.
    """

    def __init__(self, window=5, min_hits=3, match_distance=0.08):
        self.window = window
        self.min_hits = min_hits
        # Largest center move between frames, as a fraction of the tray size.
        self.match_distance = match_distance
        self.tracks = []

    def reset(self):
        self.tracks = []

    def update(self, objects):
        """Add this frame's detections; return the steady objects."""
        unmatched = list(objects)
        for track in self.tracks:
            last = track["recent"][-1]
            best, best_distance = None, self.match_distance
            for obj in unmatched:
                if obj["color"] != track["color"]:
                    continue
                distance = float(np.hypot(obj["u"] - last["u"], obj["v"] - last["v"]))
                if distance <= best_distance:
                    best, best_distance = obj, distance
            if best is not None:
                unmatched.remove(best)
                track["recent"].append(best)
                track["recent"] = track["recent"][-self.window:]
            track["seen"].append(best is not None)
            track["seen"] = track["seen"][-self.window:]

        for obj in unmatched:
            self.tracks.append({"color": obj["color"], "recent": [obj], "seen": [True]})
        # Forget objects not seen at all in the last `window` frames.
        self.tracks = [track for track in self.tracks if any(track["seen"])]

        steady = []
        for track in self.tracks:
            if sum(track["seen"]) < self.min_hits:
                continue
            recent = track["recent"]
            # Median ignores a single bad frame; a mean would be pulled by it.
            boxes = np.median([obj["box"] for obj in recent], axis=0)
            steady.append({
                "color": track["color"],
                "cx": float(np.median([obj["cx"] for obj in recent])),
                "cy": float(np.median([obj["cy"] for obj in recent])),
                "u": float(np.median([obj["u"] for obj in recent])),
                "v": float(np.median([obj["v"] for obj in recent])),
                "box": tuple(int(round(value)) for value in boxes),
                "area": float(np.median([obj["area"] for obj in recent])),
            })
        return steady


def open_capture(url, transport):
    if isinstance(url, int):
        backends = []
        for name, backend in (
            ("DirectShow", "CAP_DSHOW"),
            ("Media Foundation", "CAP_MSMF"),
            ("default", "CAP_ANY"),
        ):
            api = getattr(cv2, backend, None)
            if api is not None and all(api != existing[1] for existing in backends):
                backends.append((name, api))

        for name, api in backends:
            cap = cv2.VideoCapture(url, api)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Some Windows camera backends report an open device but return
                # black startup frames. Skip those before choosing a backend.
                for _ in range(8):
                    ok, frame = cap.read()
                    if (ok and frame is not None and frame.size and
                            (frame.max() > 2 or frame.mean() > 1)):
                        print(
                            "Connected to USB camera index {} using {}.".format(
                                url, name
                            ),
                            flush=True,
                        )
                        return cap
                print(
                    "Camera index {} opened with {}, but returned empty/black frames."
                    .format(url, name),
                    flush=True,
                )
            cap.release()
        raise SystemExit(
            "Could not get a usable image from USB camera index {}. Try another "
            "index, close apps using the camera, and check Windows Camera "
            "privacy settings.".format(url)
        )

    timeout = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 7000]
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_READ_TIMEOUT_MSEC, 7000]
    is_rtsp = url.lower().startswith("rtsp://")
    transports = ("tcp", "udp") if is_rtsp and transport == "auto" else (transport,)
    last_error = None
    for attempt_transport in transports:
        if is_rtsp:
            if attempt_transport == "udp":
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;udp|timeout;7000000"
                )
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_flags;prefer_tcp|timeout;7000000"
                )
            print("Trying RTSP over {}...".format(attempt_transport.upper()), flush=True)
        try:
            if timeout:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, timeout)
            else:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        except (TypeError, cv2.error) as exc:
            last_error = exc
            break
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("Connected{}.".format(
                " using " + attempt_transport.upper() if is_rtsp else ""
            ), flush=True)
            return cap
        cap.release()
        print("{} connection attempt failed.".format(
            attempt_transport.upper() if is_rtsp else "Video source"
        ), flush=True)

    if last_error is not None:
        raise SystemExit("OpenCV could not open the video source: {}".format(last_error))
    raise SystemExit(
        "Could not open {} over {}. Confirm the board is streaming, use the exact "
        "RTSP URL shown by its sketch, and close VLC if the camera permits only "
        "one viewer. You can force one transport with --transport tcp or udp."
        .format(url, "/".join(t.upper() for t in transports))
    )


def arrange_preview_windows():
    """Place the debug views in a two-column grid on the primary display."""
    names = (
        "Camera / tray localization",
        "Tray threshold",
        "Tray mask",
        "Image restricted to tray",
        "Rectified tray / detected objects",
        "Colored-object mask",
    )
    try:
        import ctypes
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
    except (AttributeError, ImportError, OSError):
        screen_width, screen_height = 1280, 720

    cell_width = max(320, (screen_width - 30) // 2)
    # Leave room for Windows title bars and display scaling so the bottom row
    # stays on screen.
    cell_height = max(220, (screen_height - 160) // 3)
    for index, name in enumerate(names):
        row, column = divmod(index, 2)
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(name, cell_width, cell_height)
        cv2.moveWindow(
            name,
            10 + column * (cell_width + 10),
            10 + row * (cell_height + 25),
        )


def main():
    parser = argparse.ArgumentParser(
        description="Detect colored objects inside a dynamically located black tray."
    )
    parser.add_argument("--url", default="rtsp://192.168.0.25:554")
    parser.add_argument(
        "--camera-index", type=int,
        help="Camera index (on this setup: 0=USB camera, 1=laptop camera)",
    )
    parser.add_argument("--transport", choices=("auto", "tcp", "udp"), default="auto")
    # Black has no stable hue. Ignore hue and select dark, low-saturation pixels.
    parser.add_argument("--tray-min-hue", type=int, default=0)
    parser.add_argument("--tray-max-hue", type=int, default=179)
    parser.add_argument("--tray-min-saturation", type=int, default=0)
    parser.add_argument("--tray-min-value", type=int, default=0)
    parser.add_argument("--tray-max-saturation", type=int, default=130)
    parser.add_argument("--tray-max-value", type=int, default=85,
                        help="Brightest pixel value included in the black tray mask")
    parser.add_argument("--tray-min-area-ratio", type=float, default=0.04)
    parser.add_argument("--tray-settle-seconds", type=float, default=2.0,
                        help="Wait after first tray detection before confirming it")
    parser.add_argument("--close-kernel", type=int, default=9)
    parser.add_argument("--object-min-saturation", type=int, default=70)
    parser.add_argument("--object-min-value", type=int, default=45)
    parser.add_argument("--object-min-area-ratio", type=float, default=0.0005)
    parser.add_argument("--object-max-aspect", type=float, default=1.9,
                        help="Reject elongated color blobs (default: 1.9)")
    args = parser.parse_args()

    source = args.camera_index if args.camera_index is not None else args.url
    cap = open_capture(source, args.transport)
    print("Reading {}. Press q in a preview window to quit.".format(source))
    arrange_preview_windows()
    last_report = 0.0
    failures = 0
    tray_tracker = TrayQuadTracker()
    tray_lock = TrayLock()
    object_tracker = ObjectTracker()
    settle_until = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                failures += 1
                if failures >= 2:
                    raise SystemExit(
                        "Video opened, but frames stopped arriving. Check the camera or VLC relay."
                    )
                continue
            failures = 0

            detected_quad, tray_threshold = tray_quad(
                frame,
                args.tray_min_hue,
                args.tray_max_hue,
                args.tray_min_saturation,
                args.tray_min_value,
                args.tray_max_saturation,
                args.tray_max_value,
                args.tray_min_area_ratio,
                args.close_kernel,
            )

            if (tray_tracker.current is None and not tray_lock.locked and
                    detected_quad is not None and
                    settle_until is None and args.tray_settle_seconds > 0):
                settle_until = time.monotonic() + args.tray_settle_seconds
                print(
                    "Tray candidate found. Remove your hand; confirming in {:.1f} seconds."
                    .format(args.tray_settle_seconds),
                    flush=True,
                )

            if settle_until is not None:
                remaining = settle_until - time.monotonic()
                if remaining > 0:
                    overview = frame.copy()
                    if detected_quad is not None:
                        cv2.polylines(
                            overview, [detected_quad.astype(np.int32)], True,
                            (0, 255, 255), 2,
                        )
                    cv2.putText(
                        overview, "REMOVE HAND - {:.1f}s".format(remaining),
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 255, 255), 2,
                    )
                    cv2.imshow("Camera / tray localization", overview)
                    cv2.imshow("Tray threshold", tray_threshold)
                    cv2.imshow("Tray mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                    cv2.imshow("Image restricted to tray", np.zeros_like(frame))
                    cv2.imshow("Rectified tray / detected objects", np.zeros_like(frame))
                    cv2.imshow("Colored-object mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                    continue
                settle_until = None

            quad = tray_tracker.update(detected_quad, frame.shape)
            # Once steady for 2 s the outline locks, so glare can't move it.
            now = time.monotonic()
            quad, moved_quad = tray_lock.update(quad, detected_quad, frame.shape, now)
            if moved_quad is not None:
                tray_tracker.current = moved_quad.copy()
                object_tracker.reset()
                print("Tray moved: following it, will lock again when steady.", flush=True)
            overview = frame.copy()
            if quad is None:
                object_tracker.reset()
                cv2.putText(
                    overview, "TRAY NOT FOUND", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
                )
                cv2.imshow("Camera / tray localization", overview)
                cv2.imshow("Tray threshold", tray_threshold)
                cv2.imshow("Tray mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                cv2.imshow("Image restricted to tray", np.zeros_like(frame))
                # Clear these too, so they don't keep showing an old frame.
                cv2.imshow("Rectified tray / detected objects", np.zeros_like(frame))
                cv2.imshow("Colored-object mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            outline_color = (255, 255, 0) if tray_lock.locked else (0, 255, 0)
            cv2.polylines(overview, [quad.astype(np.int32)], True, outline_color, 3)
            tray_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillConvexPoly(tray_mask, quad.astype(np.int32), 255)
            tray_only = cv2.bitwise_and(frame, frame, mask=tray_mask)
            warped, _ = rectify_tray(frame, quad)
            masks = color_masks(
                warped, args.object_min_saturation, args.object_min_value
            )
            detections = find_objects(
                warped, masks, args.object_min_area_ratio, args.object_max_aspect
            )
            # Boxes, centers and the printout use the steady objects.
            objects = object_tracker.update(detections)
            labels = warped.copy()
            # Show the brightness numbers, to debug false colors on the tray.
            tray_v, floor_v = brightness_floor(
                cv2.cvtColor(warped, cv2.COLOR_BGR2HSV), args.object_min_value
            )
            cv2.putText(
                labels, "tray brightness {}  cap needs > {}".format(tray_v, floor_v),
                (8, labels.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1,
            )
            combined_mask = np.zeros(warped.shape[:2], dtype=np.uint8)
            for color, mask in masks.items():
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            for obj in objects:
                x, y, box_w, box_h = obj["box"]
                cv2.rectangle(labels, (x, y), (x + box_w, y + box_h), (0, 255, 0), 2)
                cv2.circle(labels, (int(obj["cx"]), int(obj["cy"])), 5, (255, 0, 0), -1)
                cv2.putText(
                    labels, obj["color"], (x, max(20, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
                )

            if tray_lock.locked:
                status = "TRAY LOCKED (r = find again)"
            else:
                wait = tray_lock.seconds_to_lock(now)
                status = "FINDING TRAY" + ("" if wait is None else " - locks in {:.1f}s".format(wait))
            cv2.putText(
                overview, status, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, outline_color, 2,
            )
            cv2.imshow("Camera / tray localization", overview)
            cv2.imshow("Tray threshold", tray_threshold)
            cv2.imshow("Tray mask", tray_mask)
            cv2.imshow("Image restricted to tray", tray_only)
            cv2.imshow("Rectified tray / detected objects", labels)
            cv2.imshow("Colored-object mask", combined_mask)

            if now - last_report >= 1.0:
                print("Objects detected: {}".format(len(objects)))
                for obj in objects:
                    print(
                        "  {} center_norm=({:.3f},{:.3f}) area={:.0f}".format(
                            obj["color"], obj["u"], obj["v"], obj["area"]
                        )
                    )
                last_report = now

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                # Forget the locked outline and search for the tray again.
                tray_lock.unlock()
                tray_tracker = TrayQuadTracker()
                object_tracker.reset()
                print("Re-finding the tray (r pressed).", flush=True)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
