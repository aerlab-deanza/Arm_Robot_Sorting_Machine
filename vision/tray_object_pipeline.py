"""Find the black tray in a camera picture and the colored caps on it.
=====================================
Adjustable Variables  in the src code for different purposess:

HSV: hue 0-179 (red at both ends), saturation 0-255, value = brightness 0-255.
After a change: run with --camera-index 0, watch the named window, update
docs/computer_vision_pipeline.md.

1. Colors: make_color_masks() + constants above it. Window "Colored-object mask".
   - BLUE_MIN_HUE 100, BLUE_MAX_HUE 124. Raise MIN to drop light blue (glare).
   - BLUE_MIN_SATURATION 120. Lower = pale blue and glare count.
   - RED_MAX_HUE 10, RED_MIN_SATURATION 50. Raise MAX = skin (hue 16-23) turns red.
   - PURPLE_MIN_HUE 125, PURPLE_MAX_HUE 176. MAX is also where red's upper
     band starts (red/purple border).
   - Purple saturation: --object-min-saturation.
   - New color: add entry to masks dict.
   - 5 x 5 `kernel` removes specks. Bigger also shrinks small caps.

2. Cap brightness: min_cap_brightness(), scale_tray_brightness().
   Window "Rectified tray / detected objects".
   - TRAY_BRIGHTNESS_MARGIN 25: cap pixel must beat tray by this. Raise if tray
     shows as a color.
   - --object-min-value 45: absolute minimum cap brightness.
   - DEFAULT_TARGET_TRAY_BRIGHTNESS 50 (--tray-target-brightness, 0 = off):
     bright tray darkened to this. MIN_BRIGHTNESS_GAIN 0.4 = max darkening.

3. Find tray: find_tray_corners(), flags set in main(). Window "Tray threshold".
   - --tray-max-value 85: raise if "TRAY NOT FOUND" and tray looks bright.
   - --tray-max-saturation 130, --tray-min-area-ratio 0.04.
   - --close-kernel 9: joins gaps in dark mask.
   - In function: `aspect_ratio` 1.2-8.0, `rectangularity` 0.48 (0.58 for
     rotated-rectangle fallback), `border` rejects shapes touching image edge.

4. Tray outline steadiness: TrayOutlineSmoother args.
   Window "Camera / tray localization".
   - new_outline_weight 0.28: lower = steadier, slower.
   - hold_frames 8: missed frames that keep old outline.
   - jump_confirm_frames 3: frames to accept a big jump.
   - --tray-settle-seconds 1.25: "LOCALIZE TRAY" wait.

5. Tray lock: TrayLock, tray_moved(). Cyan = locked. `r` key unlocks.
   - lock_seconds 0.75, steady_fraction 0.015 (of image diagonal).
   - move_seconds 1.0: time a moved tray is seen before unlock.
   - tray_moved(): min_shift 0.05, size_tolerance 0.15 (bigger = glare
     counts as moved).

6. Cap detection: find_objects(). Window "Rectified tray / detected objects".
   - --object-min-area-ratio 0.0005, --object-max-aspect 1.9.
   - `min(box_w, box_h) < 12`: thinnest box (pixels).
   - 0.30 and 0.75 in duplicate check: when overlapping boxes count as one.

7. Cap steadiness: ObjectTracker args.
   - window 5, min_hits 3: shown if seen min_hits of last window frames.
   - match_distance 0.08: max move between frames (fraction of tray).

8. Camera and windows
   - open_capture() with --camera-index, --url, --transport.
   - arrange_preview_windows() names must match cv2.imshow in main().
   - _configure_ffmpeg_from_args() must run before `import cv2`.

9. Output: find_objects() builds each object (color, center_x, center_y, u, v,
   box, area). main() prints once per second. New output (records, robot
   coordinates) goes there. See docs/task_delegation.md.

Tray and caps must be on the same flat surface. u, v = fractions of tray, not
robot mm (see docs/limitation.md).

Example:
    python vision/tray_object_pipeline.py --camera-index 0
"""

import argparse
import os
import sys
import time


def _configure_ffmpeg_from_args():
    """Set FFmpeg network options from the command line, before OpenCV loads.

    OpenCV reads the ``OPENCV_FFMPEG_CAPTURE_OPTIONS`` environment variable
    only once, when it is imported, so this runs before ``import cv2``. It
    looks at ``--url`` and ``--transport`` directly in ``sys.argv``.
    """
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

import cv2  # noqa: E402  (must load after the FFmpeg options are set)
import numpy as np  # noqa: E402


def order_corners(points):
    """Put four corner points in a fixed order.

    Args:
        points: Four (x, y) points in any order and any array shape that
            reshapes to 4 x 2.

    Returns:
        A 4 x 2 float32 array ordered top-left, top-right, bottom-right,
        bottom-left.
    """
    corners = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = corners.mean(axis=0)
    angles = np.arctan2(corners[:, 1] - center[1], corners[:, 0] - center[0])
    clockwise = corners[np.argsort(angles)]
    top_left = int(np.argmin(clockwise.sum(axis=1)))
    return np.roll(clockwise, -top_left, axis=0).astype(np.float32)


def find_tray_corners(frame, min_hue, max_hue, min_saturation, min_brightness,
                      max_saturation, max_brightness, min_area_ratio, gap_fill_size):
    """Find the dark tray in a camera frame and return its four corners.

    Keeps pixels inside the given HSV limits (dark, not very colorful), joins
    small gaps, and picks the biggest, most rectangular dark shape that does
    not touch the image border.

    Args:
        frame: Camera image, BGR, shape (height, width, 3).
        min_hue: Lowest hue counted as tray (0-179).
        max_hue: Highest hue counted as tray (0-179).
        min_saturation: Lowest saturation counted as tray (0-255).
        min_brightness: Lowest brightness (HSV value) counted as tray (0-255).
        max_saturation: Highest saturation counted as tray (0-255).
        max_brightness: Highest brightness counted as tray (0-255).
        min_area_ratio: Smallest tray size, as a fraction of the frame area.
        gap_fill_size: Size in pixels of the shape used to close small gaps
            in the dark-pixel mask. Raised to an odd number of at least 3.

    Returns:
        A tuple ``(corners, dark_pixel_mask)``. ``corners`` is a 4 x 2 float32
        array (top-left, top-right, bottom-right, bottom-left), or None if no
        tray-like shape was found. ``dark_pixel_mask`` is the black-and-white
        image of pixels counted as tray, for the preview window.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    dark_pixel_mask = cv2.inRange(
        hsv,
        np.array([min_hue, min_saturation, min_brightness], dtype=np.uint8),
        np.array([max_hue, max_saturation, max_brightness], dtype=np.uint8),
    )
    kernel_size = max(3, gap_fill_size | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dark_pixel_mask = cv2.morphologyEx(dark_pixel_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(
        dark_pixel_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
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
        # tray clipped by the frame is also unsafe to straighten, so reject it.
        if (x <= border or y <= border or
                x + box_width >= width - border or
                y + box_height >= height - border):
            continue

        hull = cv2.convexHull(contour)
        min_area_rect = cv2.minAreaRect(hull)
        rect_width, rect_height = min_area_rect[1]
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
        simplified = cv2.approxPolyDP(hull, 0.04 * perimeter, True)
        if len(simplified) == 4 and cv2.isContourConvex(simplified):
            corners = order_corners(simplified)
        elif rectangularity >= 0.58:
            # Foam texture can make the outline irregular; use the rotated
            # rectangle only when the candidate itself is fairly rectangular.
            corners = order_corners(cv2.boxPoints(min_area_rect))
        else:
            continue

        center_y = (y + box_height * 0.5) / height
        score = (area / frame_area) * rectangularity * (0.8 + 0.2 * center_y)
        candidates.append((score, corners))

    if not candidates:
        return None, dark_pixel_mask
    return max(candidates, key=lambda candidate: candidate[0])[1], dark_pixel_mask


class TrayOutlineSmoother:
    """Steady the tray corners across frames.

    Small changes are blended in a little at a time, so camera noise doesn't
    make the outline shake. A big jump is only accepted after several frames
    agree on it. Through a few frames with no detection, the last outline is
    kept.

    Attributes:
        new_outline_weight: How much of each new outline is blended in (0-1).
        hold_frames: How many frames without a detection keep the old outline.
        jump_confirm_frames: How many agreeing frames a big jump needs.
        outline: Current corners (4 x 2 float32 array), or None if no tray.
        missed_frames: Frames in a row without a detection.
        pending_jump: Corners of a big jump waiting for confirmation, or None.
        pending_jump_frames: How many frames agreed on ``pending_jump``.
    """

    def __init__(self, new_outline_weight=0.28, hold_frames=8, jump_confirm_frames=3):
        """Create a smoother with no outline yet.

        Args:
            new_outline_weight: How much of each new outline is blended in.
            hold_frames: How many missed frames keep the old outline.
            jump_confirm_frames: How many agreeing frames a big jump needs.
        """
        self.new_outline_weight = new_outline_weight
        self.hold_frames = hold_frames
        self.jump_confirm_frames = jump_confirm_frames
        self.outline = None
        self.missed_frames = 0
        self.pending_jump = None
        self.pending_jump_frames = 0

    def update(self, detected_corners, frame_shape):
        """Add this frame's detection and return the steadied outline.

        Args:
            detected_corners: This frame's corners from find_tray_corners(),
                or None if the tray wasn't found.
            frame_shape: Shape of the camera frame, used to scale distances.

        Returns:
            The steadied corners (4 x 2 float32 array), or None once the tray
            has been missing for more than ``hold_frames`` frames.
        """
        if detected_corners is None:
            self.missed_frames += 1
            if self.outline is not None and self.missed_frames <= self.hold_frames:
                return self.outline.copy()
            self.outline = None
            self.pending_jump = None
            self.pending_jump_frames = 0
            return None

        detected_corners = order_corners(detected_corners)
        self.missed_frames = 0
        if self.outline is None:
            self.outline = detected_corners
            return detected_corners.copy()

        height, width = frame_shape[:2]
        frame_diagonal = float(np.hypot(width, height))
        jump = float(np.mean(np.linalg.norm(detected_corners - self.outline, axis=1)))
        if jump > frame_diagonal * 0.10:
            if self.pending_jump is not None:
                distance_to_pending = float(
                    np.mean(np.linalg.norm(detected_corners - self.pending_jump, axis=1))
                )
            else:
                distance_to_pending = float("inf")
            if distance_to_pending <= frame_diagonal * 0.035:
                self.pending_jump = 0.5 * self.pending_jump + 0.5 * detected_corners
                self.pending_jump_frames += 1
            else:
                self.pending_jump = detected_corners.copy()
                self.pending_jump_frames = 1
            if self.pending_jump_frames < self.jump_confirm_frames:
                return self.outline.copy()
            self.outline = detected_corners
            self.pending_jump = None
            self.pending_jump_frames = 0
            return self.outline.copy()

        self.pending_jump = None
        self.pending_jump_frames = 0
        self.outline = ((1.0 - self.new_outline_weight) * self.outline +
                        self.new_outline_weight * detected_corners)
        return self.outline.copy()


def _corner_distance(corners_a, corners_b):
    """Return the average distance between matching corners, in pixels.

    Args:
        corners_a: First outline, 4 x 2 array.
        corners_b: Second outline, 4 x 2 array, same corner order.

    Returns:
        Mean distance between the four corner pairs.
    """
    return float(np.mean(np.linalg.norm(corners_a - corners_b, axis=1)))


def _side_lengths(corners):
    """Return the lengths of the four sides of an outline.

    Args:
        corners: Outline, 4 x 2 array, in order around the shape.

    Returns:
        Array of 4 side lengths in pixels.
    """
    return np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)


def tray_moved(locked_corners, new_corners, frame_shape, min_shift=0.05, size_tolerance=0.15):
    """Tell whether a new outline is the same tray, clearly moved.

    Glare bends one side or corner, which changes the tray's shape. A moved
    tray keeps its shape (same side lengths) but shifts by at least
    ``min_shift`` of the image diagonal.

    This is a simple stand-in: Task 4's ``check_outline`` (same / moved /
    bent) in docs/task_delegation.md can replace it later.

    Args:
        locked_corners: The locked outline, 4 x 2 array.
        new_corners: A newly detected outline, 4 x 2 array, same corner order.
        frame_shape: Shape of the camera frame, used to scale distances.
        min_shift: Smallest average corner move that counts, as a fraction
            of the image diagonal.
        size_tolerance: Largest allowed change of each side length, as a
            fraction (0.15 means 15%).

    Returns:
        True if the tray has the same size and shape but moved clearly.
    """
    diagonal = float(np.hypot(frame_shape[1], frame_shape[0]))
    if _corner_distance(locked_corners, new_corners) < min_shift * diagonal:
        return False
    ratios = _side_lengths(new_corners) / np.maximum(_side_lengths(locked_corners), 1.0)
    return bool(np.all(np.abs(ratios - 1.0) <= size_tolerance))


class TrayLock:
    """Freeze the tray outline once it has been steady, so glare can't move it.

    Not locked: the steadied outline is used. Once it stays within
    ``steady_fraction`` of the image diagonal for ``lock_seconds``, it locks.

    Locked: the locked outline is used every frame, even while the tray is
    hidden. It unlocks when a raw detection shows the same-shaped tray clearly
    moved, in the same new place, for ``move_seconds``, or when unlock() is
    called (the 'r' key).

    Attributes:
        lock_seconds: How long the outline must stay still before locking.
        move_seconds: How long a moved tray must be seen before unlocking.
        steady_fraction: Largest corner move that still counts as still, as
            a fraction of the image diagonal.
        locked_corners: The locked outline (4 x 2 array), or None.
    """

    def __init__(self, lock_seconds=0.75, move_seconds=1.0, steady_fraction=0.015):
        """Create an unlocked lock.

        Args:
            lock_seconds: How long the outline must stay still before locking.
            move_seconds: How long a moved tray must be seen before unlocking.
            steady_fraction: Largest corner move that still counts as still,
                as a fraction of the image diagonal.
        """
        self.lock_seconds = lock_seconds
        self.move_seconds = move_seconds
        self.steady_fraction = steady_fraction
        self.locked_corners = None
        self._still_since_corners = None
        self._still_since_time = None
        self._moved_corners = None
        self._moved_since_time = None

    @property
    def locked(self):
        """bool: True while an outline is locked."""
        return self.locked_corners is not None

    def unlock(self):
        """Forget the locked outline and start watching for stillness again."""
        self.locked_corners = None
        self._still_since_corners = self._still_since_time = None
        self._moved_corners = self._moved_since_time = None

    def seconds_to_lock(self, now):
        """Return how many seconds are left before the outline locks.

        Args:
            now: Current time in seconds (time.monotonic()).

        Returns:
            Seconds left, or None if already locked or no outline is known.
        """
        if self.locked or self._still_since_time is None:
            return None
        return max(0.0, self.lock_seconds - (now - self._still_since_time))

    def update(self, smoothed_corners, detected_corners, frame_shape, now):
        """Decide which outline to use this frame.

        Args:
            smoothed_corners: Outline from TrayOutlineSmoother, or None.
            detected_corners: This frame's raw outline from
                find_tray_corners(), or None.
            frame_shape: Shape of the camera frame, used to scale distances.
            now: Current time in seconds (time.monotonic()).

        Returns:
            A tuple ``(corners_to_use, moved_corners)``. ``corners_to_use`` is
            the outline for this frame, or None if there is no tray.
            ``moved_corners`` is the new outline on the frame where the lock
            opens because the tray moved, otherwise None.
        """
        diagonal = float(np.hypot(frame_shape[1], frame_shape[0]))
        if not self.locked:
            if smoothed_corners is None:
                self._still_since_corners = self._still_since_time = None
                return None, None
            moved_since_still = (
                self._still_since_corners is None or
                _corner_distance(smoothed_corners, self._still_since_corners) >
                self.steady_fraction * diagonal
            )
            if moved_since_still:
                self._still_since_corners = smoothed_corners.copy()
                self._still_since_time = now
            elif now - self._still_since_time >= self.lock_seconds:
                self.locked_corners = smoothed_corners.copy()
            return smoothed_corners, None

        # Locked: watch raw detections for a tray that really moved.
        if detected_corners is not None:
            new_corners = order_corners(detected_corners)
            if tray_moved(self.locked_corners, new_corners, frame_shape):
                same_new_place = (
                    self._moved_corners is not None and
                    _corner_distance(new_corners, self._moved_corners) <= 0.02 * diagonal
                )
                if not same_new_place:
                    self._moved_corners, self._moved_since_time = new_corners, now
                elif now - self._moved_since_time >= self.move_seconds:
                    self.unlock()
                    return new_corners, new_corners
            else:
                self._moved_corners = self._moved_since_time = None
        return self.locked_corners.copy(), None


def straighten_tray(frame, tray_corners):
    """Warp the tray seen at an angle into a top-down rectangle.

    Args:
        frame: Camera image, BGR.
        tray_corners: Tray outline, 4 x 2 float32 array, ordered top-left,
            top-right, bottom-right, bottom-left.

    Returns:
        A tuple ``(straight_tray, transform)``. ``straight_tray`` is the
        straightened tray image, as wide and tall as the tray's longest top or
        bottom side and left or right side. ``transform`` is the 3 x 3
        perspective matrix from camera pixels to ``straight_tray`` pixels.
    """
    top_left, top_right, bottom_right, bottom_left = tray_corners
    width = int(max(np.linalg.norm(bottom_right - bottom_left),
                    np.linalg.norm(top_right - top_left)))
    height = int(max(np.linalg.norm(top_right - bottom_right),
                     np.linalg.norm(top_left - bottom_left)))
    width = max(width, 2)
    height = max(height, 2)
    target_corners = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(tray_corners, target_corners)
    return cv2.warpPerspective(frame, transform, (width, height)), transform


# Dark blue only. Glare on the dark tray reads as pale light blue (hue
# 94-104, saturation 76-132), so light blue can't be told apart from glare.
# Dark blue caps measured hue 101-115, saturation 140-255.
BLUE_MIN_HUE = 100
BLUE_MIN_SATURATION = 120

# Red's own saturation limit. The red object is a pale, pinkish red (hue 0-11,
# saturation 30-110). Red stops at hue 10, well clear of skin (hue 16-23).
RED_MIN_SATURATION = 50

# Border between purple and red at the top of the hue scale. The purple
# object is a pinkish purple (hue 168-176); the red object is hue 0-10 with
# only a few pixels at 177-179.
PURPLE_MAX_HUE = 176

# The other hue limits. Hue is a color wheel (0-179), so red sits at both ends:
# red is hue 0 to RED_MAX_HUE, and PURPLE_MAX_HUE + 1 to 179.
RED_MAX_HUE = 10
BLUE_MAX_HUE = 124
PURPLE_MIN_HUE = 125

# A cap pixel must be this much brighter than the tray's typical brightness.
# The camera's color balance drifts: the black tray has looked yellowish and,
# later, navy blue (as blue as the caps). Only brightness still told them apart.
TRAY_BRIGHTNESS_MARGIN = 25

# Brightness scaling: the tray is darkened until its median brightness is this
# value. Only darkening is done (a gain of 1 or less), and never by more than
# MIN_BRIGHTNESS_GAIN, so noise isn't boosted and bright caps aren't crushed.
DEFAULT_TARGET_TRAY_BRIGHTNESS = 50
MIN_BRIGHTNESS_GAIN = 0.4


def scale_tray_brightness(straight_tray, target_brightness=DEFAULT_TARGET_TRAY_BRIGHTNESS):
    """Darken the straightened tray picture if the tray looks too bright.

    The camera's auto exposure can make the black tray much brighter than
    usual. This multiplies the brightness (HSV value) of every pixel by one
    gain, so the tray's median brightness becomes ``target_brightness``. Hue
    and saturation are not changed, so colors keep their meaning; only
    brightness moves, and caps stay in the same brightness proportion to the
    tray.

    The gain is never above 1 (a dark tray is left alone) and never below
    ``MIN_BRIGHTNESS_GAIN``.

    Args:
        straight_tray: Straightened tray image, BGR. The straightened view is
            mostly tray, so its median brightness is the tray's.
        target_brightness: Brightness the tray should end up at (0-255).
            0 turns scaling off.

    Returns:
        A tuple ``(scaled_tray, gain)``. ``scaled_tray`` is the new BGR image
        (the input itself when the gain is 1). ``gain`` is the number every
        pixel's brightness was multiplied by.
    """
    if target_brightness <= 0:
        return straight_tray, 1.0
    hsv = cv2.cvtColor(straight_tray, cv2.COLOR_BGR2HSV)
    tray_brightness = float(np.median(hsv[..., 2]))
    if tray_brightness <= target_brightness:
        return straight_tray, 1.0
    gain = max(MIN_BRIGHTNESS_GAIN, target_brightness / tray_brightness)
    hsv[..., 2] = np.clip(hsv[..., 2].astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), gain


def min_cap_brightness(straight_tray_hsv, min_brightness):
    """Work out how bright a pixel must be to count as part of a cap.

    The straightened view is mostly tray, so its median brightness is the
    tray's. A cap pixel must be ``TRAY_BRIGHTNESS_MARGIN`` brighter than
    that, and never darker than ``min_brightness``.

    Args:
        straight_tray_hsv: Straightened tray image in HSV.
        min_brightness: Lowest brightness a cap pixel may ever have (0-255).

    Returns:
        A tuple ``(tray_brightness, cap_min_brightness)``, both 0-255.
    """
    tray_brightness = int(np.median(straight_tray_hsv[..., 2]))
    cap_min_brightness = min(255, max(min_brightness, tray_brightness + TRAY_BRIGHTNESS_MARGIN))
    return tray_brightness, cap_min_brightness


def make_color_masks(straight_tray, min_saturation, min_brightness):
    """Mark the red, blue and purple pixels in the straightened tray.

    Each mask is cleaned up: lone specks are removed and small gaps inside a
    colored region are filled.

    Args:
        straight_tray: Straightened tray image, BGR.
        min_saturation: Lowest saturation for purple (0-255). Red and blue
            use their own limits, ``RED_MIN_SATURATION`` and
            ``BLUE_MIN_SATURATION``.
        min_brightness: Lowest brightness for any cap pixel (0-255); raised
            further by min_cap_brightness().

    Returns:
        A dict from color name ("red", "blue", "purple") to a black-and-white
        mask, the same size as ``straight_tray``, where white means that color.
    """
    hsv = cv2.cvtColor(straight_tray, cv2.COLOR_BGR2HSV)
    _, cap_min_brightness = min_cap_brightness(hsv, min_brightness)

    masks = {
        # Red sits at both ends of the hue scale, so it needs two ranges.
        "red": cv2.bitwise_or(
            cv2.inRange(
                hsv, np.array([0, RED_MIN_SATURATION, cap_min_brightness], dtype=np.uint8),
                np.array([RED_MAX_HUE, 255, 255], dtype=np.uint8),
            ),
            cv2.inRange(
                hsv, np.array([PURPLE_MAX_HUE + 1, RED_MIN_SATURATION, cap_min_brightness],
                              dtype=np.uint8),
                np.array([179, 255, 255], dtype=np.uint8),
            ),
        ),
        "blue": cv2.inRange(
            hsv, np.array([BLUE_MIN_HUE, BLUE_MIN_SATURATION, cap_min_brightness], dtype=np.uint8),
            np.array([BLUE_MAX_HUE, 255, 255], dtype=np.uint8),
        ),
        "purple": cv2.inRange(
            hsv, np.array([PURPLE_MIN_HUE, min_saturation, cap_min_brightness], dtype=np.uint8),
            np.array([PURPLE_MAX_HUE, 255, 255], dtype=np.uint8),
        ),
    }

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for color, mask in masks.items():
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        masks[color] = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return masks


def find_objects(straight_tray, masks, min_object_area_ratio, max_aspect_ratio=1.9):
    """Turn colored regions into objects, and drop duplicates.

    Regions that are too small, too thin or too long are skipped. When boxes
    overlap a lot, only the biggest is kept, because one cap can show up as
    several color patches.

    Args:
        straight_tray: Straightened tray image; only its size is used.
        masks: Color masks from make_color_masks().
        min_object_area_ratio: Smallest object, as a fraction of the tray
            image area.
        max_aspect_ratio: Longest allowed long-side to short-side ratio of
            an object's box. Caps are compact; strips are not.

    Returns:
        A list of object dicts, biggest first, each with:
            color: "red", "blue" or "purple".
            center_x, center_y: Center in tray-image pixels.
            u, v: Center as a fraction of the tray width and height (0-1).
            box: (x, y, width, height) of the bounding box, in pixels.
            area: Region area in pixels.
    """
    height, width = straight_tray.shape[:2]
    minimum_area = height * width * min_object_area_ratio
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
            center_x = moments["m10"] / moments["m00"]
            center_y = moments["m01"] / moments["m00"]
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
                "center_x": center_x,
                "center_y": center_y,
                "u": center_x / width,
                "v": center_y / height,
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
        for bigger in kept:
            big_x, big_y, big_w, big_h = bigger["box"]
            overlap_left, overlap_top = max(x, big_x), max(y, big_y)
            overlap_right = min(x + box_w, big_x + big_w)
            overlap_bottom = min(y + box_h, big_y + big_h)
            intersection = (max(0, overlap_right - overlap_left) *
                            max(0, overlap_bottom - overlap_top))
            union = box_w * box_h + big_w * big_h - intersection
            smaller_box_area = min(box_w * box_h, big_w * big_h)
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
    ``min_hits`` of the last ``window`` frames, and reports the median box
    and center of its recent detections.

    Attributes:
        window: How many recent frames each object remembers.
        min_hits: In how many of those frames an object must be seen to show.
        match_distance: Largest center move between frames, as a fraction of
            the tray size, that still counts as the same object.
        tracks: One dict per remembered object, with ``color``, ``recent``
            (its last detections) and ``seen`` (True/False per recent frame).
    """

    def __init__(self, window=5, min_hits=3, match_distance=0.08):
        """Create a tracker that remembers no objects yet.

        Args:
            window: How many recent frames each object remembers.
            min_hits: In how many of those frames an object must be seen.
            match_distance: Largest center move between frames, as a
                fraction of the tray size.
        """
        self.window = window
        self.min_hits = min_hits
        self.match_distance = match_distance
        self.tracks = []

    def reset(self):
        """Forget all objects, for example when the tray is lost."""
        self.tracks = []

    def update(self, objects):
        """Add this frame's detections and return the steady objects.

        Args:
            objects: This frame's objects from find_objects().

        Returns:
            A list of steady objects, with the same keys as find_objects()
            gives. Each value is the median over the object's recent
            detections.
        """
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
                "center_x": float(np.median([obj["center_x"] for obj in recent])),
                "center_y": float(np.median([obj["center_y"] for obj in recent])),
                "u": float(np.median([obj["u"] for obj in recent])),
                "v": float(np.median([obj["v"] for obj in recent])),
                "box": tuple(int(round(value)) for value in boxes),
                "area": float(np.median([obj["area"] for obj in recent])),
            })
        return steady


def open_capture(source, transport):
    """Open a USB camera or a network video stream.

    For a USB camera, tries the Windows camera backends in turn and skips any
    that only give black frames. For RTSP with ``transport="auto"``, tries
    TCP first, then UDP.

    Args:
        source: Camera index (int, e.g. 0) or stream URL (str, e.g.
            "rtsp://192.168.0.25:554").
        transport: "auto", "tcp" or "udp". Only used for RTSP URLs.

    Returns:
        An opened cv2.VideoCapture.

    Raises:
        SystemExit: If no usable video can be opened. The message says what
            to check.
    """
    if isinstance(source, int):
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
            video = cv2.VideoCapture(source, api)
            if video.isOpened():
                video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Some Windows camera backends report an open device but return
                # black startup frames. Skip those before choosing a backend.
                for _ in range(8):
                    ok, frame = video.read()
                    if (ok and frame is not None and frame.size and
                            (frame.max() > 2 or frame.mean() > 1)):
                        print(
                            "Connected to USB camera index {} using {}.".format(
                                source, name
                            ),
                            flush=True,
                        )
                        return video
                print(
                    "Camera index {} opened with {}, but returned empty/black frames."
                    .format(source, name),
                    flush=True,
                )
            video.release()
        raise SystemExit(
            "Could not get a usable image from USB camera index {}. Try another "
            "index, close apps using the camera, and check Windows Camera "
            "privacy settings.".format(source)
        )

    timeout = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 7000]
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_READ_TIMEOUT_MSEC, 7000]
    is_rtsp = source.lower().startswith("rtsp://")
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
                video = cv2.VideoCapture(source, cv2.CAP_FFMPEG, timeout)
            else:
                video = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        except (TypeError, cv2.error) as exc:
            last_error = exc
            break
        if video.isOpened():
            video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("Connected{}.".format(
                " using " + attempt_transport.upper() if is_rtsp else ""
            ), flush=True)
            return video
        video.release()
        print("{} connection attempt failed.".format(
            attempt_transport.upper() if is_rtsp else "Video source"
        ), flush=True)

    if last_error is not None:
        raise SystemExit("OpenCV could not open the video source: {}".format(last_error))
    raise SystemExit(
        "Could not open {} over {}. Confirm the board is streaming, use the exact "
        "RTSP URL shown by its sketch, and close VLC if the camera permits only "
        "one viewer. You can force one transport with --transport tcp or udp."
        .format(source, "/".join(t.upper() for t in transports))
    )


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


def main():
    """Run the live pipeline: read frames, find the tray and caps, show them.

    Keys in a preview window: ``q`` quits, ``r`` forgets the locked tray
    outline and finds the tray again. Once per second, the steady objects
    are printed with their color and tray position.

    Raises:
        SystemExit: If the video can't be opened or frames stop arriving.
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
    parser.add_argument("--tray-min-hue", type=int, default=0)
    parser.add_argument("--tray-max-hue", type=int, default=179)
    parser.add_argument("--tray-min-saturation", type=int, default=0)
    parser.add_argument("--tray-min-value", type=int, default=0,
                        help="Darkest brightness counted as tray (0-255)")
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
    parser.add_argument("--tray-target-brightness", type=int,
                        default=DEFAULT_TARGET_TRAY_BRIGHTNESS,
                        help="Darken a too-bright tray to this brightness (0-255) "
                             "before finding caps; 0 turns it off")
    parser.add_argument("--object-min-area-ratio", type=float, default=0.0005,
                        help="Smallest cap, as a fraction of the tray image area")
    parser.add_argument("--object-max-aspect", type=float, default=1.9,
                        help="Reject elongated color blobs (default: 1.9)")
    args = parser.parse_args()

    source = args.camera_index if args.camera_index is not None else args.url
    video = open_capture(source, args.transport)
    print("Reading {}. Press q in a preview window to quit.".format(source))
    arrange_preview_windows()
    last_report = 0.0
    failures = 0
    tray_smoother = TrayOutlineSmoother()
    tray_lock = TrayLock()
    object_tracker = ObjectTracker()
    settle_until = None

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

            detected_corners, dark_pixel_mask = find_tray_corners(
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

            if (tray_smoother.outline is None and not tray_lock.locked and
                    detected_corners is not None and
                    settle_until is None and args.tray_settle_seconds > 0):
                settle_until = time.monotonic() + args.tray_settle_seconds
                print(
                    "Tray candidate found. Localizing the tray; confirming in {:.2f} seconds."
                    .format(args.tray_settle_seconds),
                    flush=True,
                )

            if settle_until is not None:
                remaining = settle_until - time.monotonic()
                if remaining > 0:
                    overview = frame.copy()
                    if detected_corners is not None:
                        cv2.polylines(
                            overview, [detected_corners.astype(np.int32)], True,
                            (0, 255, 255), 2,
                        )
                    cv2.putText(
                        overview, "LOCALIZE TRAY - {:.2f}s".format(remaining),
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 255, 255), 2,
                    )
                    cv2.imshow("Camera / tray localization", overview)
                    cv2.imshow("Tray threshold", dark_pixel_mask)
                    cv2.imshow("Tray mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                    cv2.imshow("Image restricted to tray", np.zeros_like(frame))
                    cv2.imshow("Rectified tray / detected objects", np.zeros_like(frame))
                    cv2.imshow("Colored-object mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                    continue
                settle_until = None

            smoothed_corners = tray_smoother.update(detected_corners, frame.shape)
            # Once steady for lock_seconds the outline locks, so glare can't move it.
            now = time.monotonic()
            tray_corners, moved_corners = tray_lock.update(
                smoothed_corners, detected_corners, frame.shape, now
            )
            if moved_corners is not None:
                tray_smoother.outline = moved_corners.copy()
                object_tracker.reset()
                print("Tray moved: following it, will lock again when steady.", flush=True)
            overview = frame.copy()
            if tray_corners is None:
                object_tracker.reset()
                cv2.putText(
                    overview, "TRAY NOT FOUND", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
                )
                cv2.imshow("Camera / tray localization", overview)
                cv2.imshow("Tray threshold", dark_pixel_mask)
                cv2.imshow("Tray mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                cv2.imshow("Image restricted to tray", np.zeros_like(frame))
                # Clear these too, so they don't keep showing an old frame.
                cv2.imshow("Rectified tray / detected objects", np.zeros_like(frame))
                cv2.imshow("Colored-object mask", np.zeros(frame.shape[:2], dtype=np.uint8))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            outline_color = (255, 255, 0) if tray_lock.locked else (0, 255, 0)
            cv2.polylines(overview, [tray_corners.astype(np.int32)], True, outline_color, 3)
            tray_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillConvexPoly(tray_mask, tray_corners.astype(np.int32), 255)
            tray_only = cv2.bitwise_and(frame, frame, mask=tray_mask)
            straight_tray, _ = straighten_tray(frame, tray_corners)
            # Darken the picture if the camera made the tray too bright.
            scaled_tray, brightness_gain = scale_tray_brightness(
                straight_tray, args.tray_target_brightness
            )
            masks = make_color_masks(
                scaled_tray, args.object_min_saturation, args.object_min_value
            )
            detections = find_objects(
                scaled_tray, masks, args.object_min_area_ratio, args.object_max_aspect
            )
            # Boxes, centers and the printout use the steady objects.
            objects = object_tracker.update(detections)
            detection_view = straight_tray.copy()
            # Show the brightness numbers, to debug false colors on the tray.
            tray_brightness, cap_min_brightness = min_cap_brightness(
                cv2.cvtColor(scaled_tray, cv2.COLOR_BGR2HSV), args.object_min_value
            )
            cv2.putText(
                detection_view,
                "tray brightness {} (x{:.2f})  cap needs > {}".format(
                    tray_brightness, brightness_gain, cap_min_brightness
                ),
                (8, detection_view.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1,
            )
            combined_mask = np.zeros(scaled_tray.shape[:2], dtype=np.uint8)
            for mask in masks.values():
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            for obj in objects:
                x, y, box_w, box_h = obj["box"]
                cv2.rectangle(detection_view, (x, y), (x + box_w, y + box_h), (0, 255, 0), 2)
                cv2.circle(detection_view, (int(obj["center_x"]), int(obj["center_y"])),
                           5, (255, 0, 0), -1)
                cv2.putText(
                    detection_view, obj["color"], (x, max(20, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
                )

            if tray_lock.locked:
                status = "TRAY LOCKED (r = find again)"
            else:
                wait = tray_lock.seconds_to_lock(now)
                status = "FINDING TRAY" + ("" if wait is None else " - locks in {:.2f}s".format(wait))
            cv2.putText(
                overview, status, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, outline_color, 2,
            )
            cv2.imshow("Camera / tray localization", overview)
            cv2.imshow("Tray threshold", dark_pixel_mask)
            cv2.imshow("Tray mask", tray_mask)
            cv2.imshow("Image restricted to tray", tray_only)
            cv2.imshow("Rectified tray / detected objects", detection_view)
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
                tray_smoother = TrayOutlineSmoother()
                object_tracker.reset()
                print("Re-finding the tray (r pressed).", flush=True)
    finally:
        video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
