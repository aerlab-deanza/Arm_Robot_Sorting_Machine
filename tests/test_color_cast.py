"""Tests for a camera with a blue color cast: red read as purple, and glare read as blue.

The numbers come from real screenshots. No camera needed. Run from the repo root:
python -m pytest tests/
"""
import numpy as np
import cv2

from vision.camera import lock_camera_settings
from vision.caps import find_objects, make_color_masks

H, W = 300, 600


def hsv_to_bgr(h, s, v):
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


NAVY_TRAY = hsv_to_bgr(109, 154, 66)        # the black pad under a blue cast
CRIMSON_RED = hsv_to_bgr(173, 194, 152)     # the red cap under that cast (it used to read hue 5)
OLD_RED = hsv_to_bgr(5, 253, 211)           # the red cap before the cast
PINKISH_PURPLE = hsv_to_bgr(166, 113, 151)  # the purple cap (measured in the earlier lighting)
DARK_BLUE_CAP = hsv_to_bgr(108, 200, 150)
GLARE = hsv_to_bgr(107, 142, 91)            # the pad lit brighter, in the corner


def tray_with(color, center=(300, 150), radius=40):
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = NAVY_TRAY
    cv2.circle(img, center, radius, color, -1)
    return img


def share(mask, center=(300, 150), radius=40):
    """Fraction of the disc that is white in the mask."""
    disc = np.zeros(mask.shape, np.uint8)
    cv2.circle(disc, center, radius, 255, -1)
    return float((mask[disc > 0] > 0).mean())


def test_red_under_a_blue_cast_is_red_not_purple():
    masks, _, _ = make_color_masks(tray_with(CRIMSON_RED), 70, 45)
    assert share(masks["red"]) > 0.95
    assert share(masks["purple"]) == 0.0


def test_the_pinkish_purple_cap_is_still_purple():
    masks, _, _ = make_color_masks(tray_with(PINKISH_PURPLE), 70, 45)
    assert share(masks["purple"]) > 0.95
    assert share(masks["red"]) == 0.0


def test_the_old_red_is_still_red():
    masks, _, _ = make_color_masks(tray_with(OLD_RED), 70, 45)
    assert share(masks["red"]) > 0.95
    assert share(masks["purple"]) == 0.0


def test_a_dark_blue_cap_is_still_found():
    masks, _, _ = make_color_masks(tray_with(DARK_BLUE_CAP), 70, 45)
    assert share(masks["blue"]) > 0.95


def test_glare_on_the_navy_tray_is_not_blue():
    masks, tray_brightness, cap_min = make_color_masks(tray_with(GLARE, (30, 30), 25), 70, 45)
    assert tray_brightness == 66 and cap_min == 66 + 45
    assert masks["blue"].max() == 0


def test_objects_near_the_edge_are_ignored():
    img = tray_with(CRIMSON_RED)
    cv2.circle(img, (30, 30), 25, CRIMSON_RED, -1)                 # a second blob in the corner
    masks, _, _ = make_color_masks(img, 70, 45)
    assert len(find_objects(img, masks, 0.0005)) == 2              # edge margin off: both
    kept = find_objects(img, masks, 0.0005, edge_margin=0.1)
    assert len(kept) == 1 and 0.4 < kept[0]["u"] < 0.6


class FakeCamera:
    """Records what the program asks of a camera. Pretends every setting works."""

    def __init__(self):
        self.reads = 0
        self.set_calls = []

    def read(self):
        self.reads += 1
        return True, None

    def get(self, prop):
        return {cv2.CAP_PROP_WB_TEMPERATURE: 4200.0, cv2.CAP_PROP_EXPOSURE: -6.0}[prop]

    def set(self, prop, value):
        self.set_calls.append((prop, value))
        return True


def test_lock_camera_freezes_the_current_values():
    camera = FakeCamera()
    report = lock_camera_settings(camera, warmup_frames=5)
    assert camera.reads == 5
    assert report["white_balance"] == 4200.0 and report["exposure"] == -6.0
    assert all(report[key] for key in ("white_balance_auto_off", "white_balance_value_set",
                                       "exposure_auto_off", "exposure_value_set"))
    assert (cv2.CAP_PROP_AUTO_WB, 0) in camera.set_calls
    assert (cv2.CAP_PROP_WB_TEMPERATURE, 4200.0) in camera.set_calls
    assert (cv2.CAP_PROP_EXPOSURE, -6.0) in camera.set_calls
