"""Cut pictures and numbers out of a raw camera recording for the explainer video.

    python docs/animations/arm_vision_video/make_assets.py --video arm_raw.mp4 --base 344 346

Writes into docs/animations/arm_vision_video/assets/: stage pictures of two frames (straight, bent) and
`run_stats.json` (per-frame tip, curvature, length, raw and smoothed). Every picture is
made by the real code in vision/arm_vision.py, with the same numbers.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "vision"))
import arm_vision as av  # noqa: E402

ASSETS = HERE / "assets"


def stages(frame, base, name):
    """Save the intermediate pictures of segment_arm and trace_centerline for one frame."""
    grey = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    otsu, _ = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    wall = float(np.percentile(grey, 75))
    limit = min(otsu, max(25.0, 0.40 * wall))
    _, dark = cv2.threshold(grey, limit, 255, cv2.THRESH_BINARY_INV)
    blurred = cv2.GaussianBlur(frame, (7, 7), 0).astype(np.float32)
    neutral = blurred[..., 0] > 0.25 * (blurred[..., 2] + 3.0)
    dark_neutral = np.where(neutral, dark, 0).astype(np.uint8)
    size = max(5, int(0.04 * min(dark.shape)) | 1)
    ell = lambda w: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (w, w))  # noqa: E731
    thick = cv2.morphologyEx(dark_neutral, cv2.MORPH_OPEN, ell(2 * size + 1))
    thin = cv2.bitwise_and(dark_neutral, cv2.bitwise_not(cv2.dilate(thick, ell(5))))
    thin = cv2.morphologyEx(thin, cv2.MORPH_OPEN, ell(3))
    closed = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, ell(size))
    final = av.segment_arm(frame)
    skeleton = skeletonize(final > 0)
    path = av._longest_path(skeleton, base, 0.12 * max(final.shape))
    result = av.estimate_shape(frame, base)

    out = {"frame": frame, "grey": grey, "dark": dark, "dark_neutral": dark_neutral,
           "thick": thick, "thin": thin, "closed": closed, "mask": final,
           "skeleton": (skeleton * 255).astype(np.uint8)}
    for key, img in out.items():
        cv2.imwrite(str(ASSETS / f"{name}_{key}.png"), img)
    cv2.imwrite(str(ASSETS / f"{name}_overlay.png"), av.draw_overlay(frame, result))
    info = {"otsu": float(otsu), "wall75": wall, "limit": float(limit), "kernel": int(size),
            "base": [float(base[0]), float(base[1])],
            "skeleton_path": path.tolist() if path is not None else None,
            "backbone": result["backbone"], "tip": result["tip"],
            "pcc": {k: v for k, v in result["pcc"].items()},
            "poly": {k: v for k, v in result["poly"].items()}}
    (ASSETS / f"{name}_info.json").write_text(json.dumps(info))
    return result


def main():
    """Read the recording, save stage pictures and per-frame statistics."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--base", type=int, nargs=2, required=True)
    parser.add_argument("--straight", type=int, default=0)
    parser.add_argument("--bent", type=int, default=203)
    args = parser.parse_args()
    ASSETS.mkdir(exist_ok=True)
    base = tuple(args.base)

    cap = cv2.VideoCapture(args.video)
    smoother = av.ShapeSmoother()
    rows = []
    number = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        result = av.estimate_shape(frame, base)
        used = smoother.update(result)
        row = {"frame": number, "found": result["found"], "used": bool(used)}
        if result["found"]:
            row.update(raw_tip=result["tip"], raw_kappa=result["pcc"]["kappa"],
                       raw_length=result["pcc"]["length"], poly_rms=result["poly"]["rms_px"])
        if smoother.tip is not None:
            row.update(tip=[float(v) for v in smoother.tip], kappa=float(smoother.kappa),
                       length=float(smoother.length))
        rows.append(row)
        if number == args.straight:
            stages(frame, base, "straight")
        if number == args.bent:
            stages(frame, base, "bent")
        number += 1
    (ASSETS / "run_stats.json").write_text(json.dumps(rows))
    print(number, "frames written to", ASSETS)


if __name__ == "__main__":
    main()
