"""Find the backbone curve of a black tendon arm in front of a white wall.

Steps (one frame, no camera needed - see `estimate_shape`):
    1. segment_arm       - dark pixels = arm (Otsu threshold on grey picture).
    2. trace_centerline  - walk from the base along the arm, take the middle of
                           the arm at every step. Gives ordered backbone points.
    3. fit_pcc / fit_poly_curvature - fit a constant-curvature arc (or a
                           curvature that changes along the arm) to the points.

Output coordinates: pixels, origin at the base, x right, y UP.
Run on an image or video:
    python vision/arm_vision.py --image arm.png
    python vision/arm_vision.py --video arm.mp4
    python vision/arm_vision.py --camera-index 0
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from skimage.morphology import skeletonize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_models import poly_curvature_points  # noqa: E402

# Real length of the arm in mm. Change this if the arm changes. The program uses it to
# find the picture scale (pixels per mm) by itself, so no scale option is needed.
ARM_LENGTH_MM = 300.0
# How many good frames to measure before the scale is fixed.
CALIBRATION_FRAMES = 30


def segment_arm(frame_bgr, min_area_fraction=0.002, max_arm_width_fraction=0.04,
                max_dark_fraction=0.40, min_blue_to_red=0.25):
    """Binary mask of the dark, thin arm on a bright wall.

    Args:
        frame_bgr: Camera picture (BGR).
        min_area_fraction: Blobs smaller than this fraction of the picture are dropped.
        max_arm_width_fraction: Half-width limit of the arm, as a fraction of the
            picture's short side. Thicker dark blobs (clothes, shadows) are ignored.
            Raise it if your arm looks thicker in the picture.
        min_blue_to_red: Dark pixels need blue >= this * red (skin is reddish, the arm is
            neutral). Lower it if the arm itself is dropped.
        max_dark_fraction: Arm pixels must be darker than this fraction of the wall
            brightness, even if Otsu would allow more (hands in shadow are only dark-ish).

    Returns:
        uint8 mask (0 or 255) of the thin dark pieces. Empty if nothing found.
    """
    grey = cv2.GaussianBlur(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    # An empty wall has no dark blob: skip Otsu when the picture is nearly uniform.
    if int(grey.max()) - int(grey.min()) < 40:
        return np.zeros_like(grey)
    otsu, _ = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Skin in shadow and clothes are only dark-ish: use a stricter limit when Otsu is lenient.
    wall = float(np.percentile(grey, 75))
    _, dark = cv2.threshold(grey, min(otsu, max(25.0, max_dark_fraction * wall)), 255,
                            cv2.THRESH_BINARY_INV)
    # Skin (even in shadow) is reddish: blue is clearly weaker than red. The black arm is
    # neutral. Drop reddish dark pixels, so a hand in shadow does not join the arm.
    blurred = cv2.GaussianBlur(frame_bgr, (7, 7), 0).astype(np.float32)
    neutral = blurred[..., 0] > min_blue_to_red * (blurred[..., 2] + 3.0)
    dark = np.where(neutral, dark, 0).astype(np.uint8)
    max_half = max_arm_width_fraction * min(dark.shape)
    size = max(5, int(max_half) | 1)

    def ellipse(width):
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (width, width))

    # 1. Remove THICK dark areas (jacket, shadow): opening keeps only blobs wider than the
    #    arm. Cut them away (with a small margin); the thin arm is what is left.
    thick = cv2.morphologyEx(dark, cv2.MORPH_OPEN, ellipse(2 * size + 1))
    thin = cv2.bitwise_and(dark, cv2.bitwise_not(cv2.dilate(thick, ellipse(5))))
    thin = cv2.morphologyEx(thin, cv2.MORPH_OPEN, ellipse(3))  # remove 1-2 px specks
    # 2. The white clips cut the arm into pieces: close the gaps along the arm.
    mask = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, ellipse(size))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= min_area_fraction * mask.size]
    return np.where(np.isin(labels, keep), 255, 0).astype(np.uint8)


def find_base(mask, base_xy=None):
    """Base point in pixels (x, y_down). Default: middle of the lowest rows of the mask."""
    if base_xy is not None:
        return np.array(base_xy, dtype=float)
    ys, xs = np.nonzero(mask)
    low = ys >= ys.max() - max(2, int(0.02 * (ys.max() - ys.min() + 1)))
    return np.array([xs[low].mean(), ys[low].mean()], dtype=float)


def _longest_path(skeleton, base_xy=None, max_base_distance=None):
    """Path (pixels, in order) through a skeleton picture. Side branches are ignored.

    Args:
        skeleton: Boolean skeleton picture.
        base_xy: Known base (x, y). If given, the path starts at the skeleton point
            nearest to it and runs to the farthest point of the same piece, so other
            dark shapes (sleeve, laptop) cannot win. None = the longest path anywhere.
        max_base_distance: With a base: give up if the skeleton is farther than this.
    """
    ys, xs = np.nonzero(skeleton)
    n = len(ys)
    if n < 4:
        return None
    index = -np.ones(skeleton.shape, dtype=np.int64)
    index[ys, xs] = np.arange(n)
    rows, cols, weights = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        ny, nx = ys + dy, xs + dx
        ok = (ny < skeleton.shape[0]) & (nx >= 0) & (nx < skeleton.shape[1])
        other = np.full(n, -1)
        other[ok] = index[ny[ok], nx[ok]]
        link = other >= 0
        rows.append(np.nonzero(link)[0])
        cols.append(other[link])
        weights.append(np.full(link.sum(), np.hypot(dy, dx)))
    graph = csr_matrix((np.concatenate(weights), (np.concatenate(rows), np.concatenate(cols))),
                       shape=(n, n))
    count, label = connected_components(graph, directed=False)
    if base_xy is not None:
        gap = np.hypot(xs - base_xy[0], ys - base_xy[1])
        start = int(np.argmin(gap))
        if max_base_distance is not None and gap[start] > max_base_distance:
            return None
        members = np.nonzero(label == label[start])[0]
        if len(members) < 4:
            return None
        dist, pred = dijkstra(graph, directed=False, indices=start, return_predecessors=True)
        end = members[np.argmax(np.where(np.isfinite(dist[members]), dist[members], -1))]
        path = [end]
        while path[-1] != start:
            path.append(pred[path[-1]])
        path = np.array(path[::-1])
        return np.stack([xs[path], ys[path]], axis=1).astype(float)
    best = None
    for comp in range(count):
        members = np.nonzero(label == comp)[0]
        if len(members) < 4:
            continue
        # double sweep: the farthest point from anywhere is an end of the longest path
        d0 = dijkstra(graph, directed=False, indices=members[0])
        end_a = members[np.argmax(np.where(np.isfinite(d0[members]), d0[members], -1))]
        d1, pred = dijkstra(graph, directed=False, indices=end_a, return_predecessors=True)
        end_b = members[np.argmax(np.where(np.isfinite(d1[members]), d1[members], -1))]
        if best is None or d1[end_b] > best[0]:
            path = [end_b]
            while path[-1] != end_a:
                path.append(pred[path[-1]])
            best = (d1[end_b], path[::-1])
    if best is None:
        return None
    path = np.array(best[1])
    return np.stack([xs[path], ys[path]], axis=1).astype(float)


def _smooth_and_extend(path, radius_start, radius_end, step=4.0):
    """Resample evenly, smooth lightly, and push each end out by the arm's half-width.

    A skeleton stops one half-width before the real end of the arm.
    """
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    grid = np.arange(0.0, s[-1], step)
    if len(grid) < 4:
        return None
    pts = np.stack([np.interp(grid, s, path[:, 0]), np.interp(grid, s, path[:, 1])], axis=1)
    kernel = np.ones(5) / 5
    for axis in (0, 1):  # moving average, keep the ends where they are
        padded = np.concatenate([[pts[0, axis]] * 2, pts[:, axis], [pts[-1, axis]] * 2])
        pts[:, axis] = np.convolve(padded, kernel, mode="valid")
    head = pts[0] - pts[min(4, len(pts) - 1)]
    tail = pts[-1] - pts[max(-5, -len(pts))]
    head = pts[0] + radius_start * head / (np.linalg.norm(head) + 1e-9)
    tail = pts[-1] + radius_end * tail / (np.linalg.norm(tail) + 1e-9)
    return np.vstack([head, pts, tail])


def trace_centerline(mask, base_xy=None):
    """Middle line of the arm, base first, tip last.

    Skeleton of the mask, then the longest path through it (short side branches such
    as a shadow under a hand are dropped).

    Args:
        mask: Binary arm mask from `segment_arm`.
        base_xy: Base (x, y_down) in pixels. The path end nearest to it is the base.
            None = the lower end of the path.

    Returns:
        Array (N, 2) of pixel points (x, y_down), or None if nothing arm-like was found.
    """
    if not mask.any():
        return None
    skeleton = skeletonize(mask > 0)
    path = _longest_path(skeleton, base_xy, max_base_distance=0.12 * max(mask.shape))
    if path is None:
        return None
    if base_xy is None and path[-1, 1] > path[0, 1]:
        path = path[::-1]  # image y grows downward: the lower end is the base
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    radius_start = float(dist[int(path[0, 1]), int(path[0, 0])])
    radius_end = float(dist[int(path[-1, 1]), int(path[-1, 0])])
    points = _smooth_and_extend(path, radius_start, radius_end)
    if points is None or _arc_length(points)[-1] < 5 * max(radius_start, 2.0):
        return None
    return points


def _to_y_up(points_px, base_px):
    """Pixels (y down) -> origin at base, y up."""
    out = points_px - base_px
    out[:, 1] *= -1.0
    return out


def _arc_length(points):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])


def _fit(points, order):
    """Least-squares fit of a curvature polynomial (order + 1 coefficients) to ordered points."""
    s = _arc_length(points)
    length = float(s[-1])
    k = min(3, len(points) - 1)
    angle0 = float(np.arctan2(points[k, 1], points[k, 0]))

    def model(params):
        return poly_curvature_points(params[1:], length, n=400, base_angle=params[0],
                                     base_xy=points[0])

    def residual(params):
        fitted = model(params)
        grid = np.linspace(0.0, length, len(fitted))
        return np.concatenate([np.interp(s, grid, fitted[:, 0]) - points[:, 0],
                               np.interp(s, grid, fitted[:, 1]) - points[:, 1]])

    solution = least_squares(residual, np.concatenate([[angle0], np.zeros(order + 1)]))
    rms = float(np.sqrt(np.mean(solution.fun ** 2) * 2))
    return solution.x, model(solution.x), rms, length


def fit_pcc(points):
    """Fit ONE constant-curvature arc (PCC, one section) to ordered backbone points (y up).

    Returns:
        dict: kappa (1/px), base_angle (rad), length (px), rms_px, points (fitted backbone).
    """
    params, fitted, rms, length = _fit(points, 0)
    return {"kappa": float(params[1]), "base_angle": float(params[0]), "length": length,
            "rms_px": rms, "points": fitted}


def fit_poly_curvature(points, order=2):
    """Fit curvature that changes along the arm: k(s) = c0 + c1*u + ... (u = s / length)."""
    params, fitted, rms, length = _fit(points, order)
    return {"coeffs": [float(c) for c in params[1:]], "base_angle": float(params[0]),
            "length": length, "rms_px": rms, "points": fitted}


def estimate_shape(frame_bgr, base_xy=None, px_per_mm=None):
    """Whole pipeline on one frame.

    Args:
        frame_bgr: Camera picture (BGR).
        base_xy: Base (x, y_down) in pixels, or None to find it.
        px_per_mm: Picture scale. None = results in pixels.

    Returns:
        dict with `found` (bool). If found: `base_px`, `tip` (x, y up, from base),
        `backbone` (list of [x, y]), `pcc` (kappa, base_angle, length, rms_px, fit),
        `poly` (coeffs, rms_px, fit). Lengths in pixels, or mm if `px_per_mm` is given.
        Curvature is in 1/pixel (or 1/mm).
    """
    mask = segment_arm(frame_bgr)
    traced = trace_centerline(mask, base_xy)
    if traced is None:
        return {"found": False}
    base_px = traced[0].copy()
    pts = _to_y_up(traced, base_px)
    pcc = fit_pcc(pts)
    poly = fit_poly_curvature(pts, 2)
    k = 1.0 if px_per_mm is None else 1.0 / px_per_mm
    return {
        "found": True,
        "base_px": [float(base_px[0]), float(base_px[1])],
        "px_per_mm": px_per_mm,
        "tip": [float(pts[-1, 0] * k), float(pts[-1, 1] * k)],
        "backbone": (pts * k).tolist(),
        "pcc": {"kappa": pcc["kappa"] / k, "base_angle": pcc["base_angle"],
                "length": pcc["length"] * k, "rms_px": pcc["rms_px"],
                "fit": (pcc["points"] * k).tolist()},
        "poly": {"coeffs": [c / k for c in poly["coeffs"]], "rms_px": poly["rms_px"],
                 "fit": (poly["points"] * k).tolist()},
    }


def draw_overlay(frame_bgr, result, tip=None, kappa=None, px_per_mm=None):
    """Draw traced backbone (green), PCC arc (yellow) and tip (red) on a copy of the picture.

    Also writes a label panel (top left) with the smoothed tip (x, y) and kappa.

    Args:
        frame_bgr: Camera picture.
        result: Output of `estimate_shape`.
        tip: Smoothed tip (x, y up, from the base) or None. Shown as "-" if None.
        kappa: Smoothed curvature or None. Shown as "-" if None.
        px_per_mm: Picture scale, or None while it is still being measured.

    Returns:
        A copy of the picture with the drawings.
    """
    out = frame_bgr.copy()
    if px_per_mm is None:
        lines = ("measuring scale...", "keep the arm in view")
    else:
        x_y = "-" if tip is None else f"{tip[0]:.1f}, {tip[1]:.1f}"
        kappa_text = "-" if kappa is None else f"{kappa:.5f}"
        lines = (f"tip (x, y) = {x_y} mm", f"kappa = {kappa_text} 1/mm")
    width = max(cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0] for t in lines)
    cv2.rectangle(out, (0, 0), (width + 20, 24 * len(lines) + 8), (0, 0, 0), -1)  # dark panel: readable on any background
    for row, text in enumerate(lines):
        cv2.putText(out, text, (10, 24 + 24 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    if not result.get("found"):
        return out
    bx, by = result["base_px"]
    scale = result["px_per_mm"] or 1.0

    def to_px(p):
        return int(round(bx + p[0] * scale)), int(round(by - p[1] * scale))

    for key, color, width in (("backbone", (0, 200, 0), 2), ("fit", (0, 255, 255), 1)):
        pts = result["backbone"] if key == "backbone" else result["pcc"]["fit"]
        cv2.polylines(out, [np.array([to_px(p) for p in pts])], False, color, width)
    cv2.circle(out, to_px(result["tip"]), 6, (0, 0, 255), -1)
    return out


def read_frames(cap):
    """Yield frames from an open cv2.VideoCapture until it stops giving pictures."""
    while True:
        ok, frame = cap.read()
        if not ok:
            return
        yield frame


class ShapeSmoother:
    """Steady the numbers from frame to frame and skip bad frames.

    A frame is "bad" when the arm is not found, the fit is poor, or the arm
    length jumps (hand or shadow joined the arm). Then the last good values are
    held for up to `hold_frames` frames.

    Attributes:
        alpha: Blend of the new frame (0-1). Smaller = steadier but slower.
        hold_frames: How many bad frames in a row to hold the last values.
        tip: Smoothed tip (x, y up) or None.
        kappa: Smoothed curvature or None.
        length: Smoothed arm length or None.
    """

    def __init__(self, alpha=0.4, hold_frames=10, max_length_jump=0.25, max_fit_error=0.03):
        self.alpha = alpha
        self.hold_frames = hold_frames
        self.max_length_jump = max_length_jump
        self.max_fit_error = max_fit_error
        self.tip = self.kappa = self.length = None
        self.bad_in_a_row = 0

    def update(self, result):
        """Feed one `estimate_shape` result. Returns True if the frame was used."""
        good = result.get("found", False)
        if good:
            length = result["pcc"]["length"]
            # use the flexible fit for the error: an S-shaped arm is not a bad frame
            good = result["poly"]["rms_px"] <= self.max_fit_error * length
            if good and self.length is not None:
                good = abs(length - self.length) <= self.max_length_jump * self.length
        if good:
            new = (np.array(result["tip"]), result["pcc"]["kappa"], result["pcc"]["length"])
            if self.tip is None:
                self.tip, self.kappa, self.length = new
            else:
                a = self.alpha
                self.tip = (1 - a) * self.tip + a * new[0]
                self.kappa = (1 - a) * self.kappa + a * new[1]
                self.length = (1 - a) * self.length + a * new[2]
            self.bad_in_a_row = 0
            return True
        self.bad_in_a_row += 1
        if self.bad_in_a_row > self.hold_frames:  # lost for too long: forget, start fresh
            self.tip = self.kappa = self.length = None
        return False


def parse_args():
    """Command-line options."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image")
    source.add_argument("--video")
    source.add_argument("--camera-index", type=int)
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("X", "Y", "W", "H"),
                        help="use only this part of the picture (cuts black borders of a screen recording)")
    parser.add_argument("--base", type=int, nargs=2, metavar=("X", "Y"),
                        help="arm base in pixels (after the crop). Without it: click it in the first picture")
    parser.add_argument("--record", metavar="FILE.avi",
                        help="save the raw camera picture (no drawings) to a video file (.avi is safest)")
    return parser.parse_args()


def pick_base(frame):
    """Show a picture, let the user click the arm base. Returns (x, y), or None if no click."""
    clicked = []
    window = "click the arm base, then press any key"
    cv2.imshow(window, frame)
    cv2.setMouseCallback(window, lambda event, x, y, *_: clicked.append((x, y))
                         if event == cv2.EVENT_LBUTTONDOWN else None)
    cv2.waitKey(0)
    cv2.destroyWindow(window)
    return clicked[-1] if clicked else None


def main():
    """Command line: run on an image, a video file or a camera. One JSON line per frame."""
    args = parse_args()
    cap = None
    if args.image:
        frames = iter([cv2.imread(args.image)])
    else:
        if args.video:
            cap = cv2.VideoCapture(args.video)
        elif sys.platform == "win32":
            cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)  # more reliable on Windows
        else:
            cap = cv2.VideoCapture(args.camera_index)
        if not cap.isOpened():
            sys.exit("Cannot open the camera/video. Try another --camera-index (0, 1, 2) "
                     "and close other programs that use the camera.")
        frames = read_frames(cap)

    def crop(frame):
        if args.crop and frame is not None:
            x, y, w, h = args.crop
            return frame[y:y + h, x:x + w]
        return frame

    base = tuple(args.base) if args.base else None
    smoother = ShapeSmoother()
    px_per_mm = None  # found from ARM_LENGTH_MM in the first CALIBRATION_FRAMES good frames
    lengths_px = []
    writer = None
    count = 0
    try:
        for number, frame in enumerate(frames):
            if frame is None:
                break
            frame = crop(frame)
            if number == 0 and base is None and not args.no_gui:
                base = pick_base(frame)
            count += 1
            if args.record:
                if writer is None:
                    fps = cap.get(cv2.CAP_PROP_FPS) if cap else 0.0
                    fps = fps if fps > 1 else 30.0  # some cameras report 0 or -1
                    # .avi (MJPG) stays readable even if the program is killed; .mp4 does not
                    codec = "MJPG" if args.record.lower().endswith(".avi") else "mp4v"
                    writer = cv2.VideoWriter(args.record, cv2.VideoWriter_fourcc(*codec), fps,
                                             (frame.shape[1], frame.shape[0]))
                writer.write(frame)  # raw picture, before any drawing
            result = estimate_shape(frame, base, px_per_mm)
            used = smoother.update(result)
            line = {"frame": number, "found": result["found"], "used": used}
            if px_per_mm is None:
                if used:
                    lengths_px.append(result["pcc"]["length"])
                if len(lengths_px) >= (1 if args.image else CALIBRATION_FRAMES):
                    px_per_mm = float(np.median(lengths_px)) / ARM_LENGTH_MM
                    smoother = ShapeSmoother()  # restart: the numbers are now in mm
                    result = estimate_shape(frame, base, px_per_mm)
                    smoother.update(result)
                    print(f"scale: {px_per_mm:.3f} px/mm (arm length {ARM_LENGTH_MM:g} mm)", file=sys.stderr)
                line["calibrating"] = px_per_mm is None
            if px_per_mm is not None and smoother.tip is not None:
                line["px_per_mm"] = round(px_per_mm, 4)
                line.update(tip=[round(float(v), 2) for v in smoother.tip],
                            kappa=round(float(smoother.kappa), 6), length=round(float(smoother.length), 1))
            print(json.dumps(line), flush=True)
            if not args.no_gui:
                cv2.imshow("arm", draw_overlay(frame, result, smoother.tip, smoother.kappa, px_per_mm))
                if cv2.waitKey(0 if args.image else 1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass  # Ctrl+C: stop cleanly so the recording is saved
    finally:
        if writer is not None:
            writer.release()
    if count == 0:
        sys.exit("No picture received. Wrong --camera-index, or the camera is busy.")


if __name__ == "__main__":
    main()
