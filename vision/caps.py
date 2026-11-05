"""Find red, blue and purple caps on the straightened tray, and steady their boxes."""

import cv2
import numpy as np


# Dark blue only. Glare on the dark tray reads as pale light blue (hue
# 94-104, saturation 76-132), so light blue can't be told apart from glare.
# Dark blue caps measured hue 101-115, saturation 140-255.
BLUE_MIN_HUE = 100
BLUE_MIN_SATURATION = 120

# Red's own saturation limit. The red cap is strongly colored (hue 0-8,
# saturation 226-255). A hand in shadow reads hue 7-10, saturation 60-200, so this stays high. Pale pinkish reds (saturation 30-110) are not detected.
RED_MIN_SATURATION = 150

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
        A tuple ``(masks, tray_brightness, cap_min_brightness)``. ``masks`` is
        a dict from color name ("red", "blue", "purple") to a black-and-white
        mask, the same size as ``straight_tray``, where white means that color.
        The two numbers (0-255) are the tray's brightness and the lowest
        brightness a cap pixel needed, from min_cap_brightness().
    """
    hsv = cv2.cvtColor(straight_tray, cv2.COLOR_BGR2HSV)
    tray_brightness, cap_min_brightness = min_cap_brightness(hsv, min_brightness)

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
    return masks, tray_brightness, cap_min_brightness


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
