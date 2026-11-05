"""Find the black tray in a camera picture and the colored caps on it.

Runs on the PC: camera frame -> find the tray -> steady and lock its outline ->
straighten it -> find red, blue and purple caps -> steady the
boxes -> report each cap's color and position as a fraction of the
tray (u across, v down, 0-1).

The steps live in three files next to this one:
    camera.py - open a USB camera or a network stream.
    tray.py   - find, steady, lock and straighten the tray.
    caps.py   - find caps by color, and steady their boxes.
This file shows the live windows and prints the results.

Example:
    python vision/tray_object_pipeline.py --camera-index 0
"""

import argparse
import time

# Works both as a script (python vision/tray_object_pipeline.py) and when
# imported as vision.tray_object_pipeline. camera must load first: it sets the
# FFmpeg options before OpenCV loads.
try:
    from .camera import open_capture
    from .tray import (  # noqa: F401  (re-exported so old imports keep working)
        TrayLock, TrayOutlineSmoother, find_tray_corners, order_corners,
        straighten_tray, tray_moved,
    )
    from .caps import (  # noqa: F401  (re-exported so old imports keep working)
        ObjectTracker, find_objects, make_color_masks, min_cap_brightness,
    )
except ImportError:
    from camera import open_capture
    from tray import (  # noqa: F401
        TrayLock, TrayOutlineSmoother, find_tray_corners, order_corners,
        straighten_tray, tray_moved,
    )
    from caps import (  # noqa: F401
        ObjectTracker, find_objects, make_color_masks, min_cap_brightness,
    )

import cv2  # noqa: E402
import numpy as np  # noqa: E402


def arrange_preview_windows():
    """Place the six debug windows in a two-column grid on the main screen.

    Uses the Windows screen size when available, otherwise assumes
    1280 x 720.
    """
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


class FrameResult:
    """What one camera frame produced, ready to show on screen.

    Attributes:
        overview: Camera image with the tray outline and status text drawn on it.
        dark_pixel_mask: Black-and-white tray threshold from find_tray_corners().
        tray_found: True if a tray outline was used for this frame.
        tray_mask: Black-and-white picture, white inside the tray outline, or
            None when there is no tray.
        tray_only: Camera image with everything outside the tray outline
            blacked out, or None when there is no tray.
        detection_view: Straightened tray with boxes and labels drawn on it, or
            None when there is no tray.
        color_mask: All color masks in one black-and-white image (white = a cap
            color), or None when there is no tray.
        objects: Steady caps from ObjectTracker (dicts with ``color``, ``u``,
            ``v``, ``center_x``, ``center_y``, ``box``, ``area``). Empty when
            there is no tray.
    """

    def __init__(self, overview, dark_pixel_mask, tray_found=False, tray_mask=None,
                 tray_only=None, detection_view=None, color_mask=None, objects=None):
        """Store the pictures and caps of one frame.

        Args:
            overview: Camera image with outline and status text drawn on it.
            dark_pixel_mask: Black-and-white tray threshold.
            tray_found: True if a tray outline was used.
            tray_mask: White inside the tray outline, or None.
            tray_only: Camera image outside the tray blacked out, or None.
            detection_view: Straightened tray with boxes drawn, or None.
            color_mask: Combined color mask, or None.
            objects: Steady caps, or None for no caps.
        """
        self.overview = overview
        self.dark_pixel_mask = dark_pixel_mask
        self.tray_found = tray_found
        self.tray_mask = tray_mask
        self.tray_only = tray_only
        self.detection_view = detection_view
        self.color_mask = color_mask
        self.objects = objects if objects is not None else []


class TrayCapPipeline:
    """The whole vision pipeline for one camera, one frame at a time.

    It keeps what must be remembered between frames (the steady tray outline,
    the tray lock, the cap tracker, the settle timer). It does not read the
    camera or open windows, so tests can feed it drawn pictures.

    Attributes:
        args: Settings from parse_args().
        tray_smoother: TrayOutlineSmoother for the tray corners.
        tray_lock: TrayLock that freezes the outline once it is steady.
        object_tracker: ObjectTracker that steadies the cap boxes.
        settle_until: Time (seconds) when the first-sighting wait ends, or None.
    """

    def __init__(self, args):
        """Create a pipeline that has not seen a tray yet.

        Args:
            args: Settings from parse_args().
        """
        self.args = args
        self.tray_smoother = TrayOutlineSmoother()
        self.tray_lock = TrayLock()
        self.object_tracker = ObjectTracker()
        self.settle_until = None

    def reset_tray(self):
        """Forget the locked outline and search for the tray again."""
        self.tray_lock.unlock()
        self.tray_smoother = TrayOutlineSmoother()
        self.object_tracker.reset()

    def process_frame(self, frame, now):
        """Run every step on one camera frame.

        Args:
            frame: Camera image, BGR.
            now: Current time in seconds (time.monotonic()). Passed in so
                tests can control the clock.

        Returns:
            A FrameResult with the pictures to show and the steady caps.
        """
        args = self.args
        detected_corners, dark_pixel_mask = find_tray_corners(
            frame,
            0, 179,  # any hue: black has no stable hue
            0, 0,    # no lower limit on saturation or brightness
            args.tray_max_saturation,
            args.tray_max_value,
            args.tray_min_area_ratio,
            args.close_kernel,
        )
        overview = frame.copy()

        # First sighting: wait a moment before trusting the tray.
        if (self.tray_smoother.outline is None and not self.tray_lock.locked and
                detected_corners is not None and
                self.settle_until is None and args.tray_settle_seconds > 0):
            self.settle_until = now + args.tray_settle_seconds
            print(
                "Tray candidate found. Localizing the tray; confirming in {:.2f} seconds."
                .format(args.tray_settle_seconds),
                flush=True,
            )
        if self.settle_until is not None:
            remaining = self.settle_until - now
            if remaining > 0:
                if detected_corners is not None:
                    cv2.polylines(
                        overview, [detected_corners.astype(np.int32)], True,
                        (0, 255, 255), 2,
                    )
                cv2.putText(
                    overview, "LOCALIZE TRAY - {:.2f}s".format(remaining),
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2,
                )
                return FrameResult(overview, dark_pixel_mask)
            self.settle_until = None

        smoothed_corners = self.tray_smoother.update(detected_corners, frame.shape)
        # Once steady for lock_seconds the outline locks, so glare can't move it.
        tray_corners, moved_corners = self.tray_lock.update(
            smoothed_corners, detected_corners, frame.shape, now
        )
        if moved_corners is not None:
            self.tray_smoother.outline = moved_corners.copy()
            self.object_tracker.reset()
            print("Tray moved: following it, will lock again when steady.", flush=True)
        if tray_corners is None:
            self.object_tracker.reset()
            cv2.putText(
                overview, "TRAY NOT FOUND", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
            )
            return FrameResult(overview, dark_pixel_mask)

        outline_color = (255, 255, 0) if self.tray_lock.locked else (0, 255, 0)
        cv2.polylines(overview, [tray_corners.astype(np.int32)], True, outline_color, 3)
        if self.tray_lock.locked:
            status = "TRAY LOCKED (r = find again)"
        else:
            wait = self.tray_lock.seconds_to_lock(now)
            status = "FINDING TRAY" + ("" if wait is None else " - locks in {:.2f}s".format(wait))
        cv2.putText(
            overview, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, outline_color, 2,
        )

        tray_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(tray_mask, tray_corners.astype(np.int32), 255)
        tray_only = cv2.bitwise_and(frame, frame, mask=tray_mask)

        straight_tray, _ = straighten_tray(frame, tray_corners)
        masks, tray_brightness, cap_min_brightness = make_color_masks(
            straight_tray, args.object_min_saturation, args.object_min_value
        )
        detections = find_objects(
            straight_tray, masks, args.object_min_area_ratio, args.object_max_aspect
        )
        # Boxes, centers and the printout use the steady objects.
        objects = self.object_tracker.update(detections)

        detection_view = straight_tray.copy()
        # Show the brightness numbers, to debug false colors on the tray.
        cv2.putText(
            detection_view,
            "tray brightness {}  cap needs > {}".format(
                tray_brightness, cap_min_brightness
            ),
            (8, detection_view.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (255, 255, 255), 1,
        )
        for obj in objects:
            x, y, box_w, box_h = obj["box"]
            cv2.rectangle(detection_view, (x, y), (x + box_w, y + box_h), (0, 255, 0), 2)
            cv2.circle(detection_view, (int(obj["center_x"]), int(obj["center_y"])),
                       5, (255, 0, 0), -1)
            cv2.putText(
                detection_view, obj["color"], (x, max(20, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
            )
        color_mask = np.zeros(straight_tray.shape[:2], dtype=np.uint8)
        for mask in masks.values():
            color_mask = cv2.bitwise_or(color_mask, mask)
        return FrameResult(overview, dark_pixel_mask, True, tray_mask, tray_only,
                           detection_view, color_mask, objects)


def show_results(frame, result):
    """Show a FrameResult in the six preview windows.

    Without a tray, the tray windows are cleared so they don't keep
    showing an old frame.

    Args:
        frame: Camera image, BGR; only its size is used for the blank views.
        result: FrameResult from TrayCapPipeline.process_frame().
    """
    tray_mask = result.tray_mask
    if tray_mask is None:
        tray_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    tray_only = result.tray_only
    if tray_only is None:
        tray_only = np.zeros_like(frame)
    detection_view = result.detection_view
    if detection_view is None:
        detection_view = np.zeros_like(frame)
    color_mask = result.color_mask
    if color_mask is None:
        color_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.imshow("Camera / tray localization", result.overview)
    cv2.imshow("Tray threshold", result.dark_pixel_mask)
    cv2.imshow("Tray mask", tray_mask)
    cv2.imshow("Image restricted to tray", tray_only)
    cv2.imshow("Rectified tray / detected objects", detection_view)
    cv2.imshow("Colored-object mask", color_mask)


def parse_args(argv=None):
    """Read the command-line flags.

    Args:
        argv: List of flags, or None to read them from the command line.

    Returns:
        The settings (argparse.Namespace).
    """
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
    # In HSV, "value" means brightness (0-255).
    parser.add_argument("--tray-max-saturation", type=int, default=130)
    parser.add_argument("--tray-max-value", type=int, default=85,
                        help="Brightest brightness counted as tray (0-255)")
    parser.add_argument("--tray-min-area-ratio", type=float, default=0.04,
                        help="Smallest tray, as a fraction of the frame area")
    parser.add_argument("--tray-settle-seconds", type=float, default=1.25,
                        help="Wait after first tray detection before confirming it")
    parser.add_argument("--close-kernel", type=int, default=9,
                        help="Size in pixels used to fill small gaps in the tray mask")
    parser.add_argument("--object-min-saturation", type=int, default=70,
                        help="Lowest saturation for purple (red and blue have their own)")
    parser.add_argument("--object-min-value", type=int, default=45,
                        help="Lowest brightness for any cap pixel (0-255)")
    parser.add_argument("--object-min-area-ratio", type=float, default=0.0005,
                        help="Smallest cap, as a fraction of the tray image area")
    parser.add_argument("--object-max-aspect", type=float, default=1.9,
                        help="Reject elongated color blobs (default: 1.9)")
    return parser.parse_args(argv)


def main():
    """Run the live pipeline: read frames, find the tray and caps, show them.

    Keys in a preview window: ``q`` quits, ``r`` forgets the locked tray
    outline and finds the tray again. Once per second, the steady objects
    are printed with their color and tray position.

    Raises:
        SystemExit: If the video can't be opened or frames stop arriving.
    """
    args = parse_args()
    source = args.camera_index if args.camera_index is not None else args.url
    video = open_capture(source, args.transport)
    print("Reading {}. Press q in a preview window to quit.".format(source))
    arrange_preview_windows()
    pipeline = TrayCapPipeline(args)
    last_report = 0.0
    failures = 0

    try:
        while True:
            ok, frame = video.read()
            if not ok:
                failures += 1
                if failures >= 2:
                    raise SystemExit(
                        "Video opened, but frames stopped arriving. Check the camera or VLC relay."
                    )
                continue
            failures = 0

            now = time.monotonic()
            result = pipeline.process_frame(frame, now)
            show_results(frame, result)

            if result.tray_found and now - last_report >= 1.0:
                print("Objects detected: {}".format(len(result.objects)))
                for obj in result.objects:
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
                pipeline.reset_tray()
                print("Re-finding the tray (r pressed).", flush=True)
    finally:
        video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
