"""Tests for a black tray that looks dark blue next to a bright board, with a dark floor behind it.

No camera needed. Run from the repo root:  python -m pytest tests/
"""
import numpy as np
import cv2
import pytest

from vision.tray import find_tray_corners
from vision.tray_object_pipeline import TrayCapPipeline, parse_args

ARGS = (0, 179, 0, 0, 255, 85, 0.04, 9)          # the pipeline defaults: brightness only
REGION = (0.04, 0.36, 0.96, 0.95)                # below the floor, around the tray
TRUE = np.float32([[130, 180], [690, 180], [690, 440], [130, 440]])


def hsv_to_bgr(h, s, v):
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


FLOOR = hsv_to_bgr(10, 150, 40)       # dark brown floor
BOARD = (240, 240, 240)               # bright white board
PAD = hsv_to_bgr(111, 160, 45)        # the black pad, turned dark blue by the camera (saturation 160)


def picture(with_floor):
    img = np.full((480, 800, 3), BOARD, np.uint8)
    if with_floor:
        img[:170] = FLOOR             # only a thin bright strip separates the floor from the pad
    cv2.rectangle(img, (130, 180), (690, 440), PAD, -1)
    return img


def corner_error(corners):
    return float(np.abs(corners - TRUE).max())


def test_a_dark_blue_pad_is_found_by_brightness_alone():
    corners, _ = find_tray_corners(picture(with_floor=False), *ARGS)
    assert corners is not None and corner_error(corners) < 3


def test_the_old_saturation_limit_lost_the_pad():
    corners, _ = find_tray_corners(picture(with_floor=False), 0, 179, 0, 0, 130, 85, 0.04, 9)
    assert corners is None            # saturation 160 is above 130: this is what went wrong before


def test_without_a_region_the_dark_floor_joins_the_tray():
    corners, _ = find_tray_corners(picture(with_floor=True), *ARGS)
    assert corners is None            # the joined shape touches the image border and is rejected


def test_a_region_keeps_the_floor_out():
    corners, _ = find_tray_corners(picture(with_floor=True), *ARGS, region=REGION)
    assert corners is not None and corner_error(corners) < 4


def test_the_pipeline_uses_the_region():
    flags = ["--tray-region", "0.04,0.36,0.96,0.95"]
    pipeline = TrayCapPipeline(parse_args(flags))
    now, result = 0.0, None
    while now < 3.0:
        result = pipeline.process_frame(picture(with_floor=True), now)
        now += 0.1
    assert result.tray_found and result.tray_state == "locked"


def test_the_region_flag_checks_its_numbers():
    assert parse_args(["--tray-region", "0.1,0.2,0.9,0.8"]).tray_region == (0.1, 0.2, 0.9, 0.8)
    for bad in ("0.5,0.5,0.2,0.9", "a,b,c,d", "0.1,0.1,0.9", "0.1,0.1,0.9,1.5"):
        with pytest.raises(SystemExit):
            parse_args(["--tray-region", bad])


def test_saturation_is_off_by_default_and_no_region_by_default():
    args = parse_args([])
    assert args.tray_max_saturation == 255 and args.tray_region is None
