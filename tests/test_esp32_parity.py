"""Checks that the shared board code (firmware/tray_cap_core) gives the same answers as the Python pipeline.

The core is plain C++. This test builds it for the PC with g++, runs it on
drawn 320 x 240 pictures, and compares with the Python pipeline on the same
pictures. Skipped when g++ is not installed.

Run from the repo root:  python -m pytest tests/test_esp32_parity.py
"""
import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from vision.tray_object_pipeline import TrayCapPipeline, parse_args

FIRMWARE = Path(__file__).resolve().parent.parent / "firmware" / "tray_cap_core"
SOURCES = ["pc_test/pc_test.cpp", "tc_image.cpp", "tc_tray.cpp", "tc_caps.cpp", "tc_pipeline.cpp", "tc_jpeg.cpp"]
TJPGD = FIRMWARE / "third_party" / "tjpgd" / "tjpgd.c"

RED, BLUE, PURPLE = (40, 40, 220), (200, 60, 60), (180, 80, 160)   # BGR
DARK = (30, 30, 30)


@pytest.fixture(scope="module")
def pc_test(tmp_path_factory):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is not installed")
    work = tmp_path_factory.mktemp("core")
    exe = work / "pc_test.exe"
    c = subprocess.run([shutil.which("gcc") or "gcc", "-O2", "-c", "-o", str(work / "tjpgd.o"), str(TJPGD)],
                       capture_output=True, text=True)
    assert c.returncode == 0, c.stderr
    build = subprocess.run([compiler, "-std=c++17", "-O2", "-o", str(exe)] + [str(FIRMWARE / s) for s in SOURCES]
                           + [str(work / "tjpgd.o")], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    return exe


def picture(caps, cable=False):
    img = np.full((240, 320, 3), 160, np.uint8)
    cv2.rectangle(img, (40, 40), (280, 190), DARK, -1)
    if cable:
        cv2.rectangle(img, (160, 12), (163, 44), DARK, -1)        # a thin cable touching the top edge
    for x, y, radius, color in caps:
        cv2.circle(img, (x, y), radius, color, -1)
    return img


def skewed_picture():
    img = np.full((240, 320, 3), 160, np.uint8)
    cv2.fillConvexPoly(img, np.array([[70, 40], [250, 40], [290, 200], [30, 200]]), DARK)
    cv2.circle(img, (150, 110), 14, RED, -1)
    cv2.circle(img, (200, 150), 14, PURPLE, -1)
    return img


def run_python(img):
    pipeline = TrayCapPipeline(parse_args([]))
    now, result = 0.0, None
    while now < 3.0:
        result = pipeline.process_frame(img, now)
        now += 0.1
    caps = sorted((o["color"], o["u"], o["v"], o["box"][2], o["box"][3]) for o in result.objects)
    return result.tray_state, caps


def run_cpp(exe, img, tmp_path, jpeg=False, extra=()):
    if jpeg:
        raw = tmp_path / "picture.jpg"
        cv2.imwrite(str(raw), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    else:
        raw = tmp_path / "picture.rgb"
        cv2.cvtColor(img, cv2.COLOR_BGR2RGB).tofile(raw)
    out = subprocess.run([str(exe), str(raw), "320", "240", "3", "100", "--min-side", "12", *extra],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout.strip().splitlines()[-1])
    caps = sorted((c["color"], c["u"], c["v"], c["box"][2], c["box"][3]) for c in data["caps"])
    return data["tray"], caps


def assert_same(py, cpp):
    assert py[0] == cpp[0]
    assert [c[0] for c in py[1]] == [c[0] for c in cpp[1]]          # same colors
    for a, b in zip(py[1], cpp[1]):
        assert abs(a[1] - b[1]) < 0.02 and abs(a[2] - b[2]) < 0.02   # positions within 2% of the tray
        assert abs(a[3] - b[3]) <= 4 and abs(a[4] - b[4]) <= 4       # box sizes within 4 pixels


def test_one_red_cap(pc_test, tmp_path):
    img = picture([(120, 110, 14, RED)])
    assert_same(run_python(img), run_cpp(pc_test, img, tmp_path))


def test_three_colors(pc_test, tmp_path):
    img = picture([(90, 100, 13, RED), (160, 130, 13, BLUE), (220, 90, 14, PURPLE)])
    py, cpp = run_python(img), run_cpp(pc_test, img, tmp_path)
    assert_same(py, cpp)
    assert [c[0] for c in cpp[1]] == ["blue", "purple", "red"]


def test_a_skewed_tray(pc_test, tmp_path):
    img = skewed_picture()
    assert_same(run_python(img), run_cpp(pc_test, img, tmp_path))


def test_no_tray_means_no_caps(pc_test, tmp_path):
    img = np.full((240, 320, 3), 160, np.uint8)
    assert run_cpp(pc_test, img, tmp_path) == ("not_found", [])


def test_the_board_code_ignores_a_cable_like_task_1(pc_test, tmp_path):
    """Python does not have the four-main-corners fix yet, so only compare the board code with itself."""
    caps = [(120, 110, 14, RED)]
    clean = run_cpp(pc_test, picture(caps), tmp_path)
    with_cable = run_cpp(pc_test, picture(caps, cable=True), tmp_path)
    assert with_cable[0] == "locked"
    assert abs(clean[1][0][1] - with_cable[1][0][1]) < 0.01 and abs(clean[1][0][2] - with_cable[1][0][2]) < 0.01


def test_rgb565_pixels_give_the_same_answer(pc_test, tmp_path):
    img = picture([(90, 100, 13, RED), (160, 130, 13, BLUE), (220, 90, 14, PURPLE)])
    assert_same(run_python(img), run_cpp(pc_test, img, tmp_path, extra=["--rgb565"]))


def test_a_jpeg_picture_gives_the_same_answer(pc_test, tmp_path):
    """The AMB82 board decodes a JPEG first. Compare with Python on the raw picture."""
    img = picture([(90, 100, 13, RED), (160, 130, 13, BLUE), (220, 90, 14, PURPLE)])
    assert_same(run_python(img), run_cpp(pc_test, img, tmp_path, jpeg=True))


def test_a_lamp_on_the_tray_gives_the_same_answer(pc_test, tmp_path):
    """Grey glare on one corner of the pad: both raise the brightness limit the same way."""
    img = picture([(200, 90, 13, RED), (230, 150, 13, BLUE)])
    glare = np.zeros((240, 320), np.uint8)
    cv2.circle(glare, (40, 190), 80, 255, -1)
    pad = np.zeros((240, 320), np.uint8)
    cv2.rectangle(pad, (40, 40), (280, 190), 255, -1)
    img[(glare > 0) & (pad > 0)] = (120, 120, 120)
    py, cpp = run_python(img), run_cpp(pc_test, img, tmp_path)
    assert_same(py, cpp)
    assert cpp[0] == "locked" and [c[0] for c in cpp[1]] == ["blue", "red"]
