"""Tests for the whole vision pipeline on drawn pictures. No camera needed.

Run from the repo root:  python -m pytest tests/
"""
import numpy as np
import cv2

from vision.tray_object_pipeline import TrayCapPipeline, parse_args

# BGR colors.
RED = (40, 40, 220)
BLUE = (200, 60, 60)
PALE_PINKISH_RED = (170, 170, 255)   # like a hand in shadow: reddish but pale


def picture(cap_colors=()):
    """A grey table, a black tray, and one round cap per color."""
    img = np.full((480, 800, 3), 160, np.uint8)
    cv2.rectangle(img, (100, 80), (700, 380), (30, 30, 30), -1)
    for i, color in enumerate(cap_colors):
        cv2.circle(img, (250 + 200 * i, 230), 30, color, -1)
    return img


def run(img, seconds, step=0.1):
    """Feed the same picture for some seconds of fake time.

    Returns:
        The pipeline and the last FrameResult.
    """
    pipeline = TrayCapPipeline(parse_args([]))
    result, now = None, 0.0
    while now <= seconds:
        result = pipeline.process_frame(img, now)
        now += step
    return pipeline, result


def test_tray_is_found_after_the_first_sighting_wait():
    img = picture()
    pipeline = TrayCapPipeline(parse_args([]))
    assert not pipeline.process_frame(img, 0.0).tray_found      # waiting 1.25 s
    assert pipeline.process_frame(img, 1.3).tray_found


def test_red_and_blue_caps_are_found():
    img = picture([RED, BLUE])
    _, result = run(img, 2.0)
    assert sorted(obj["color"] for obj in result.objects) == ["blue", "red"]
    for obj in result.objects:
        assert 0.0 < obj["u"] < 1.0 and 0.0 < obj["v"] < 1.0


def test_outline_locks_when_steady():
    img = picture()
    pipeline, result = run(img, 3.0)
    assert pipeline.tray_lock.locked
    assert result.overview.shape == img.shape
    assert result.tray_mask is not None and result.tray_only is not None


def test_no_tray_gives_no_caps():
    img = np.full((480, 800, 3), 160, np.uint8)
    pipeline = TrayCapPipeline(parse_args([]))
    result = pipeline.process_frame(img, 0.0)
    assert not result.tray_found
    assert result.objects == [] and result.detection_view is None


def test_pale_reddish_color_is_not_a_cap():
    img = picture([PALE_PINKISH_RED])
    _, result = run(img, 2.0)
    assert result.objects == []
