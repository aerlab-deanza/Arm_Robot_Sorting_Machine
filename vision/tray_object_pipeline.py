"""Locate a moving white tray, rectify it, and find colored objects on it.

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
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;7000000"
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
              max_saturation, min_area_ratio, close_kernel):
    """Find the pale cyan tray and return a plausible four-corner outline."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    threshold = cv2.inRange(
        hsv,
        np.array([min_hue, min_saturation, min_value], dtype=np.uint8),
        np.array([max_hue, max_saturation, 255], dtype=np.uint8),
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
        if not 1.2 <= aspect_ratio <= 5.5 or rectangularity < 0.48:
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


def color_masks(warped, min_saturation, min_value):
    """Return basic HSV masks for red, orange, and purple project objects."""
    hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
    smin, vmin = min_saturation, min_value

    red = cv2.bitwise_or(
        cv2.inRange(
            hsv, np.array([0, smin, vmin], dtype=np.uint8),
            np.array([7, 255, 255], dtype=np.uint8),
        ),
        cv2.inRange(
            hsv, np.array([170, smin, vmin], dtype=np.uint8),
            np.array([179, 255, 255], dtype=np.uint8),
        ),
    )
    masks = {
        "red": red,
        "orange": cv2.inRange(
            hsv, np.array([8, smin, vmin], dtype=np.uint8),
            np.array([24, 255, 255], dtype=np.uint8),
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
    # One physical item can produce separate hue regions (especially the
    # orange ball under glare). Keep the largest candidate when boxes overlap.
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
            # Small red/orange patches inside a larger ball are color
            # variation or glare, not separate objects.
            if ((union and intersection / union >= 0.30) or
                    overlap_of_smaller >= 0.75):
                duplicate = True
                break
        if not duplicate:
            kept.append(obj)
    return kept


def open_capture(url, transport):
    if isinstance(url, int):
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("Connected to USB camera index {}.".format(url), flush=True)
            return cap
        cap.release()
        raise SystemExit(
            "Could not open USB camera index {}. Check that the camera is "
            "connected and not in use by another app.".format(url)
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


def main():
    parser = argparse.ArgumentParser(
        description="Detect colored objects inside a dynamically located white tray."
    )
    parser.add_argument("--url", default="rtsp://192.168.0.25:554")
    parser.add_argument(
        "--camera-index", type=int,
        help="USB camera index (usually 0); use instead of --url",
    )
    parser.add_argument("--transport", choices=("auto", "tcp", "udp"), default="auto")
    parser.add_argument("--tray-min-hue", type=int, default=70)
    parser.add_argument("--tray-max-hue", type=int, default=112)
    parser.add_argument("--tray-min-saturation", type=int, default=10)
    parser.add_argument("--tray-min-value", type=int, default=160)
    parser.add_argument("--tray-max-saturation", type=int, default=150)
    parser.add_argument("--tray-min-area-ratio", type=float, default=0.04)
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
    last_report = 0.0
    failures = 0
    tray_tracker = TrayQuadTracker()

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
                args.tray_min_area_ratio,
                args.close_kernel,
            )
            quad = tray_tracker.update(detected_quad, frame.shape)
            overview = frame.copy()
            if quad is None:
                cv2.putText(
                    overview, "TRAY NOT FOUND", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
                )
                cv2.imshow("Camera / tray localization", overview)
                cv2.imshow("Tray threshold", tray_threshold)
                cv2.imshow("Tray mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                cv2.imshow("Image restricted to tray", np.zeros_like(frame))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            cv2.polylines(overview, [quad.astype(np.int32)], True, (0, 255, 0), 3)
            tray_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillConvexPoly(tray_mask, quad.astype(np.int32), 255)
            tray_only = cv2.bitwise_and(frame, frame, mask=tray_mask)
            warped, _ = rectify_tray(frame, quad)
            masks = color_masks(
                warped, args.object_min_saturation, args.object_min_value
            )
            objects = find_objects(
                warped, masks, args.object_min_area_ratio, args.object_max_aspect
            )

            labels = warped.copy()
            combined_mask = np.zeros(warped.shape[:2], dtype=np.uint8)
            for color, mask in masks.items():
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            for obj in objects:
                x, y, box_w, box_h = obj["box"]
                cv2.rectangle(labels, (x, y), (x + box_w, y + box_h), (0, 255, 0), 2)
                cv2.circle(labels, (int(obj["cx"]), int(obj["cy"])), 5, (255, 0, 0), -1)
                cv2.putText(
                    labels, obj["color"], (x, max(20, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2,
                )

            cv2.putText(
                overview, "TRAY FOUND", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2,
            )
            cv2.imshow("Camera / tray localization", overview)
            cv2.imshow("Tray mask", tray_mask)
            cv2.imshow("Image restricted to tray", tray_only)
            cv2.imshow("Rectified tray / detected objects", labels)
            cv2.imshow("Colored-object mask", combined_mask)

            now = time.monotonic()
            if now - last_report >= 1.0:
                print("Objects detected: {}".format(len(objects)))
                for obj in objects:
                    print(
                        "  {} center_norm=({:.3f},{:.3f}) area={:.0f}".format(
                            obj["color"], obj["u"], obj["v"], obj["area"]
                        )
                    )
                last_report = now

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
