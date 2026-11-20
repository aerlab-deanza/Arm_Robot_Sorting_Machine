"""Tests with drawn pictures (no camera). Run from repo root: python -m pytest tests/test_modeling.py"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from arm_vision import estimate_shape  # noqa: E402
from shape_models import cosserat_planar_static, pcc_points  # noqa: E402


def draw_arm(kappa, length=300.0, width=22, size=(480, 640), base=(320, 440)):
    """White wall with a black arc arm. Returns (picture, true tip, y up, from base)."""
    img = np.full((*size, 3), 235, np.uint8)
    pts = pcc_points(kappa, length, 200)
    px = np.stack([base[0] + pts[:, 0], base[1] - pts[:, 1]], axis=1)
    cv2.polylines(img, [np.round(px).astype(np.int32)], False, (20, 20, 20), width, cv2.LINE_AA)
    return img, pts[-1]


def test_pcc_recovers_curvature_and_tip():
    for kappa in (0.0, 0.004, -0.006, 0.01):
        img, tip = draw_arm(kappa)
        r = estimate_shape(img)
        assert r["found"]
        assert abs(r["pcc"]["kappa"] - kappa) < 0.0008
        assert np.hypot(r["tip"][0] - tip[0], r["tip"][1] - tip[1]) < 15  # pixels (the traced end stops about half an arm width early)


def test_empty_wall_gives_not_found():
    assert not estimate_shape(np.full((480, 640, 3), 235, np.uint8))["found"]


def test_cosserat_without_gravity_is_constant_curvature():
    cos = cosserat_planar_static(1.0, 2.0, 1.0)
    pcc = pcc_points(0.5, 1.0, len(cos))
    assert np.max(np.abs(cos - pcc)) < 1e-6


def test_gravity_pulls_tip_down():
    free = cosserat_planar_static(1.0, 2.0, 1.0)
    heavy = cosserat_planar_static(1.0, 2.0, 1.0, weight_per_length=1.0)
    assert heavy[-1, 1] < free[-1, 1]


def test_thick_dark_sleeve_is_ignored_and_base_picks_the_arm():
    img, tip = draw_arm(0.004)
    cv2.rectangle(img, (0, 150), (150, 330), (40, 45, 40), -1)  # big dark sleeve
    cv2.line(img, (40, 100), (200, 60), (20, 20, 20), 12)       # thin dark cable, longer? no: shorter
    r = estimate_shape(img, base_xy=(320, 440))
    assert r["found"]
    assert abs(r["pcc"]["kappa"] - 0.004) < 0.001
