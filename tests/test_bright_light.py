"""Tests for a black tray that looks grey where a lamp shines on it.

The usual limit (brightness 85) loses the lit part of the pad. The pipeline then
raises the limit step by step until the outline is clean (find_tray_corners_any_light).
No camera needed. Run from the repo root:  python -m pytest tests/
"""
import cv2
import numpy as np

from vision.tray import find_tray_corners, find_tray_corners_any_light
from vision.tray_object_pipeline import TrayCapPipeline, parse_args

PAD = (150, 90, 490, 290)           # left, top, right, bottom
TRUE = np.float32([[150, 90], [490, 90], [490, 290], [150, 290]])


def picture(glare_radius=0, floor=225):
    """A black pad on a bright floor, with grey glare on its bottom-left corner."""
    img = np.full((360, 640, 3), floor, np.uint8)
    cv2.rectangle(img, PAD[:2], PAD[2:], (40, 40, 40), -1)
    if glare_radius:
        glare = np.zeros(img.shape[:2], np.uint8)
        cv2.circle(glare, (PAD[0], PAD[3]), glare_radius, 255, -1)
        pad = np.zeros(img.shape[:2], np.uint8)
        cv2.rectangle(pad, PAD[:2], PAD[2:], 255, -1)
        img[(glare > 0) & (pad > 0)] = (120, 120, 120)      # the lit part reads brightness 120
    return img


def corner_error(corners):
    return float(np.abs(corners - TRUE).max())


def test_the_usual_limit_cuts_off_the_lit_corner():
    corners, _ = find_tray_corners(picture(glare_radius=150), 0, 179, 0, 0, 255, 85, 0.04, 9)
    assert corners is not None and corner_error(corners) > 50     # this is the problem


def test_raising_the_limit_finds_the_whole_pad():
    for radius in (120, 150, 220):
        corners, _, limit = find_tray_corners_any_light(picture(radius), 255, 85, 145, 0.04, 9)
        assert corners is not None and corner_error(corners) < 4, radius
        assert limit > 85 or radius < 150     # a small glare is filled by the gap filling


def test_normal_light_keeps_the_usual_limit():
    corners, _, limit = find_tray_corners_any_light(picture(), 255, 85, 145, 0.04, 9)
    assert limit == 85 and corner_error(corners) < 4


def test_raising_can_be_turned_off():
    corners, _, limit = find_tray_corners_any_light(picture(150), 255, 85, 85, 0.04, 9)
    assert limit == 85 and corner_error(corners) > 50


def test_the_pipeline_locks_on_the_whole_lit_pad():
    pipeline = TrayCapPipeline(parse_args([]))
    img, now, result = picture(150), 0.0, None
    while now < 3.0:
        result = pipeline.process_frame(img, now)
        now += 0.1
    assert result.tray_state == "locked"
    assert pipeline.last_dark_limit > 85
