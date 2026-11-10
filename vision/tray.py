"""Find the black tray, steady and lock its outline, and straighten it."""

import cv2
import numpy as np


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
                      max_saturation, max_brightness, min_area_ratio, gap_fill_size,
                      region=None):
    """Find the dark tray in a camera frame and return its four corners.

    Keeps pixels inside the given HSV limits (dark), joins small gaps, and
    picks the biggest, most rectangular dark shape that does not touch the
    border of the image (or of the search region, if one is given).

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
        region: Optional search region ``(left, top, right, bottom)`` as
            fractions of the frame (0-1). Everything outside it is ignored,
            so a dark floor or chair can't join the tray. The region acts
            like the image border: a shape touching it is rejected. None
            searches the whole frame.

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
    height, width = frame.shape[:2]
    left, top, right, bottom = 0, 0, width, height
    if region is not None:
        left, top = int(region[0] * width), int(region[1] * height)
        right, bottom = int(region[2] * width), int(region[3] * height)
        inside = np.zeros_like(dark_pixel_mask)
        inside[top:bottom, left:right] = 255
        dark_pixel_mask = cv2.bitwise_and(dark_pixel_mask, inside)
    kernel_size = max(3, gap_fill_size | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dark_pixel_mask = cv2.morphologyEx(dark_pixel_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(
        dark_pixel_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    frame_area = float(frame.shape[0] * frame.shape[1])
    border = max(4, int(min(height, width) * 0.008))
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area / frame_area < min_area_ratio:
            continue

        x, y, box_width, box_height = cv2.boundingRect(contour)
        # Bright windows and monitor areas often touch the image border. A
        # tray clipped by the frame is also unsafe to straighten, so reject it.
        if (x <= left + border or y <= top + border or
                x + box_width >= right - border or
                y + box_height >= bottom - border):
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
