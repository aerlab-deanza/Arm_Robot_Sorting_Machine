"""Tests for the whole vision pipeline on drawn pictures. No camera needed.

Run from the repo root:  python -m pytest tests/
"""
import json

import numpy as np
import cv2

from vision.tray_object_pipeline import TrayCapPipeline, parse_args, result_to_json

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
    assert not pipeline.process_frame(img, 0.0).tray_found      # waiting 0.5 s
    assert pipeline.process_frame(img, 0.6).tray_found


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


# ---------------------------------------------------------------- more cases

def hsv_to_bgr(h, s, v):
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


LIGHT_BLUE_GLARE = hsv_to_bgr(100, 100, 200)   # glare on the dark tray reads pale light blue
SHADOWED_HAND = hsv_to_bgr(9, 110, 150)        # reddish but not strongly colored


def feed(pipeline, img, start, seconds, step=0.1):
    """Feed the same picture to a pipeline. Returns (next start time, last result)."""
    result, now = None, start
    while now < start + seconds:
        result = pipeline.process_frame(img, now)
        now += step
    return now, result


def moved_picture(dx):
    """The same black tray, shifted sideways by dx pixels."""
    img = np.full((480, 800, 3), 160, np.uint8)
    cv2.rectangle(img, (100 + dx, 80), (700 + dx, 380), (30, 30, 30), -1)
    return img


def test_glare_is_not_a_cap():
    img = picture()
    cv2.circle(img, (400, 140), 25, LIGHT_BLUE_GLARE, -1)
    _, result = run(img, 2.0)
    assert result.tray_found and result.objects == []


def test_shadowed_hand_is_not_a_cap():
    img = picture()
    cv2.circle(img, (600, 300), 30, SHADOWED_HAND, -1)
    _, result = run(img, 2.0)
    assert result.tray_found and result.objects == []


def test_moved_tray_is_followed_and_locked_again():
    pipeline = TrayCapPipeline(parse_args([]))
    now, _ = feed(pipeline, moved_picture(0), 0.0, 3.0)
    assert pipeline.tray_lock.locked
    before = pipeline.tray_lock.locked_corners[:, 0].mean()
    feed(pipeline, moved_picture(80), now, 3.0)           # same tray, 80 px to the right
    assert pipeline.tray_lock.locked
    after = pipeline.tray_lock.locked_corners[:, 0].mean()
    assert 70 < after - before < 90


def test_cap_hidden_for_a_few_frames_comes_back():
    visible = picture([RED])
    hidden = visible.copy()
    cv2.rectangle(hidden, (200, 170), (300, 290), (30, 30, 30), -1)   # a black arm over the cap
    pipeline = TrayCapPipeline(parse_args([]))
    now, result = feed(pipeline, visible, 0.0, 2.0, step=1 / 30)
    assert len(result.objects) == 1
    step = 1 / 30
    for frames_hidden in (1, 2, 3):                        # seen in 3 of the last 5 frames is enough
        result = pipeline.process_frame(hidden, now)
        now += step
        assert len(result.objects) == (1 if frames_hidden < 3 else 0)
    for frames_back in (1, 2, 3):
        result = pipeline.process_frame(visible, now)
        now += step
        assert len(result.objects) == (0 if frames_back < 3 else 1)


def test_locked_tray_is_searched_less_often(monkeypatch):
    import vision.tray_object_pipeline as module
    calls = {"n": 0}
    real = module.find_tray_corners

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "find_tray_corners", counting)
    pipeline = TrayCapPipeline(parse_args([]))
    img = picture()
    now, _ = feed(pipeline, img, 0.0, 3.0)
    assert pipeline.tray_lock.locked
    calls["n"] = 0
    feed(pipeline, img, now, 1.0, step=1 / 30)             # 30 frames while locked
    assert 3 <= calls["n"] <= 8                            # about every 0.2 s, not every frame


def test_tray_state_names():
    img = picture()
    pipeline = TrayCapPipeline(parse_args([]))
    assert pipeline.process_frame(img, 0.0).tray_state == "settling"
    assert pipeline.process_frame(img, 0.6).tray_state == "finding"
    _, result = feed(pipeline, img, 0.7, 2.0)
    assert result.tray_state == "locked"
    assert TrayCapPipeline(parse_args([])).process_frame(
        np.full((480, 800, 3), 160, np.uint8), 0.0).tray_state == "not_found"


def test_json_line_for_programs():
    _, result = run(picture([RED]), 2.0)
    data = json.loads(result_to_json(7, 1730000000000, result))
    assert list(data) == ["frame", "time_ms", "tray", "caps"]
    assert data["frame"] == 7 and data["time_ms"] == 1730000000000 and data["tray"] == "locked"
    assert len(data["caps"]) == 1
    cap = data["caps"][0]
    assert list(cap) == ["color", "u", "v", "center_x", "center_y", "box", "area"]
    assert cap["color"] == "red" and 0 < cap["u"] < 1 and 0 < cap["v"] < 1
    empty = TrayCapPipeline(parse_args([])).process_frame(np.full((480, 800, 3), 160, np.uint8), 0.0)
    assert json.loads(result_to_json(1, 2, empty)) == {"frame": 1, "time_ms": 2, "tray": "not_found", "caps": []}
