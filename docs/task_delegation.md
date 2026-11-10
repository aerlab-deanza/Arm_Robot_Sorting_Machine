## Task 1: Make the tray outline ignore cables

![Task 1: keep the four main corners](images/tasks/task-1.gif)

**Your goal:** when a cable or a shadow touches the tray, the cyan outline still sits exactly on the tray's 4 corners.

**What you need:** Python and this repo for steps 1-5. No camera. For step 6: the camera, the tray and a cable.

**Steps:**
1. **Make your branch** `task1-corners`.
2. **Add the test.** Create `tests/test_tray_corners.py` with the test in Code help below. Run `python -m pytest tests/test_tray_corners.py`. The cable tests **fail**: that is the problem you are fixing.
3. **Write `four_main_corners(hull)`** in `vision/tray.py`, above `find_tray_corners`. It gets the outline's corner points. While there are more than 4, it removes the one that sticks out the least: the corner whose triangle with its two neighbors is smallest. A thin cable sticks out very little, so it goes first.
4. **Use it.** In `find_tray_corners`, replace the 4 `approxPolyDP` lines with the 3 new lines from Code help.
5. **Run all tests:** `python -m pytest tests/`. Everything passes, the new tests too.
6. **Try the real tray.** Put a cable behind it. Run `python vision/tray_object_pipeline.py --camera-index 0`, press `r`, and wait for "TRAY LOCKED". The cyan outline should touch the 4 tray corners.
7. **Push** (see How to push).

**This does not fix:** an object sitting right on a tray corner. That really changes the outline.

**You're done when:**

| Check | How to check | Pass |
| --- | --- | --- |
| Code works | `python -m pytest tests/` | All tests pass |
| Drawn trays | The 4 drawn tests: clean tray, thin cable, thick object, dark blob on an edge | Corners within 3 pixels of the true corners |
| Real tray | Step 6 | The cyan outline touches all 4 tray corners |

**How to push:**
```
git add vision/tray.py tests/test_tray_corners.py
git commit -m "Task 1: keep the four main corners"
git push -u origin task1-corners
```

<details>
<summary><b>Code help</b> (click to open)</summary>

**File:** `vision/tray.py`
```python
def four_main_corners(hull):
    """Reduce a convex outline (from cv2.convexHull) to its 4 most important corners."""
```

**Steps:**
1. Make a list of the hull's points: `points = [tuple(p) for p in hull.reshape(-1, 2).astype(np.float64)]`.
2. `while len(points) > 4:`
   - For each point, work out the triangle area with its neighbors `before = points[i - 1]` and `after = points[(i + 1) % len(points)]`:
     `abs((x - bx) * (ay - by) - (ax - bx) * (y - by)) / 2`
   - `del points[...]` the one with the smallest area (`np.argmin`).
3. Return `np.array(points, dtype=np.float32).reshape(-1, 1, 2)`.
4. In `find_tray_corners`, replace these lines (the `perimeter`, `simplified` and `if len(simplified) == 4 ...` lines):
   ```python
   perimeter = cv2.arcLength(hull, True)
   simplified = cv2.approxPolyDP(hull, 0.04 * perimeter, True)
   if len(simplified) == 4 and cv2.isContourConvex(simplified):
       corners = order_corners(simplified)
   ```
   with:
   ```python
   simplified = four_main_corners(hull)
   if cv2.contourArea(simplified) >= 0.9 * cv2.contourArea(hull):
       corners = order_corners(simplified)
   ```
   Keep the `elif rectangularity >= 0.58:` fallback after it. The new check keeps the four corners only if they still cover at least 90% of the hull. If not, the shape is not a tray, and the old fallback decides.

**Fake data and test:** `tests/test_tray_corners.py`
```python
import numpy as np, cv2
from vision.tray import find_tray_corners

TRUE = np.float32([[150, 90], [650, 90], [720, 380], [80, 380]])   # a tray seen at an angle
ARGS = (0, 179, 0, 0, 130, 85, 0.04, 9)                              # pipeline defaults
DARK = (30, 30, 30)

def picture():
    img = np.full((480, 800, 3), 160, np.uint8)                      # grey table
    cv2.fillConvexPoly(img, TRUE.astype(np.int32), DARK)             # black tray
    return img

def corner_error(img):
    corners, _ = find_tray_corners(img, *ARGS)
    assert corners is not None
    return float(np.abs(corners - TRUE).max())

def test_clean_tray():
    assert corner_error(picture()) < 3

def test_thin_cable():
    img = picture()
    cv2.rectangle(img, (400, 20), (406, 100), DARK, -1)              # 6 pixels wide, sticks up 70
    assert corner_error(img) < 3

def test_thick_object():
    img = picture()
    cv2.rectangle(img, (400, 60), (430, 100), DARK, -1)
    assert corner_error(img) < 3

def test_blob_on_the_top_edge():
    img = picture()
    cv2.circle(img, (300, 90), 20, DARK, -1)
    assert corner_error(img) < 3
```

</details>


<details>
<summary><b>Why is this needed?</b> (click to open)</summary>

A thin dark thing touching the tray, like a cable or a shadow, adds a spike to the black-and-white tray picture. The program expects 4 corners. The spike is a fifth one, so the program gives up and uses a big box around everything. The outline is too big, every cap position is measured against it, and the lock keeps it that way for the whole run.

![A thin object can make the tray outline wrong](images/limits/limit-1-problem.gif)

A real case: a cable behind the tray made the outline too big, and the lock kept it.

![A cable behind the tray made the outline too big](images/findings/08-wrong-lock.png)

- Today the program simplifies the outline with `cv2.approxPolyDP`. When that does not give 4 corners, it falls back to `cv2.minAreaRect`.
- A tested version of the fix took a cable's corner error from 70 pixels to 0, and all existing tests still passed.
- `--tray-region` (a search box) helps only when the cable is outside the box.

</details>

---

## Task 2: Measure the cap colors

![Task 2: calibrate the cap colors](images/tasks/task-2.gif)

**Your goal:** in your real light, the program finds every cap with the right color, and finds nothing on an empty tray.

**What you need:** Python and this repo for steps 1-6. No camera. For steps 7-9: the camera, the tray, all real caps, and the final lights.

**Steps:**
1. **Make your branch** `task2-colors`.
2. **Add the test.** Create `tests/test_colors.py` with the test in Code help. Run it: it fails, because the functions don't exist yet.
3. **Write the measuring code** in a new file `vision/calibrate_colors.py`: `measure_color`, `save_colors`, `load_colors` (Code help steps 1-4). `measure_color` gets a picture and the spots you clicked, and returns the range of colors at those spots.
4. **Let the program use it.** In `vision/caps.py`, `make_color_masks` gets an optional `color_ranges` (Code help step 5). With no colors file, nothing changes.
5. **Run all tests:** `python -m pytest tests/`. Everything passes.
6. **Add the clicking tool** at the bottom of `vision/calibrate_colors.py` (Code help step 6).
7. **Measure the real caps.** Put them on the tray, in the final light. Run `python vision/calibrate_colors.py --camera-index 0`. Press `r`, `b` or `p` to choose a color, then click 5 or more spots on each cap of that color, shaded sides too. Press `s` to save `vision/colors.json`.
8. **Ask a teammate** to read the numbers in `vision/colors.json`. Color rules decide what counts as a cap, so a second person checks them.
9. **Check** with the table below. Then push, including `vision/colors.json`.

Do steps 7-9 again whenever the light, the camera or the caps change.

**This does not fix:** two caps whose colors look the same to the camera. Use clearly different caps.

**You're done when:**

| Check | How to check | Pass |
| --- | --- | --- |
| Code works | `python -m pytest tests/` | All tests pass |
| Drawn caps | The drawn tests in `tests/test_colors.py` | Each measured range covers at least 95% of its own cap, and none of the tray or the other caps |
| Every cap found | Put each cap color in 10 places across the tray | Found with the right color 10 out of 10 times |
| No false caps | Run on an empty tray for 1 minute | 0 caps found |
| Checked by a person | Step 8 | Approved |

**How to push:**
```
git add vision/calibrate_colors.py vision/caps.py vision/colors.json tests/test_colors.py
git commit -m "Task 2: calibrate cap colors"
git push -u origin task2-colors
```

<details>
<summary><b>Code help</b> (click to open)</summary>

**File:** `vision/calibrate_colors.py`
```python
def measure_color(straight_tray_bgr, points, radius=6, margin=4):
    """Picture + clicked points → {"hue": [[low, high], ...], "min_saturation": n, "min_value": n}."""

def save_colors(ranges, path="vision/colors.json"): ...
def load_colors(path="vision/colors.json"):
    """{"red": ..., "blue": ..., "purple": ...}, or None if the file is missing."""
```

**Steps:**
1. `measure_color`: convert to HSV (`cv2.cvtColor(..., cv2.COLOR_BGR2HSV)`). For each point take the pixels inside a disk of `radius`. Put all pixels in one list.
2. Hue is a circle. Red is near 0 **and** near 179, so a plain minimum and maximum would give 0 to 179. Move the hue first: `shifted = (hue + 90) % 180`. Now red sits in the middle. Take the 2nd and 98th percentile (`np.percentile`), add the `margin`, and move it back: `(value - 90) % 180`. If the low end is bigger than the high end, the range wraps: save it as two ranges, `[0, high]` and `[low, 179]`.
3. `min_saturation`: the 2nd percentile of the saturation minus `margin * 2`. Same for `min_value`.
4. `save_colors` / `load_colors`: a JSON file with the three colors.
5. In `vision/caps.py`: `make_color_masks` gets an optional `color_ranges` argument. If it is `None`, use `load_colors()`. If that is also `None` (no file), run today's code exactly as it is: it has extra rules that a plain range cannot say, such as strongly colored pixels in the hue band 165-176 counting as red and not purple. Only when ranges are given, build each mask with `cv2.inRange` for every hue range, and join them with `cv2.bitwise_or`.
6. The tool (`if __name__ == "__main__":`): open the camera, find and straighten the tray (use `TrayCapPipeline` and `straighten_tray`), show the straightened tray, and use `cv2.setMouseCallback` to collect clicks for the chosen color.

**Fake data and test:** `tests/test_colors.py`
```python
import numpy as np, cv2
from vision.calibrate_colors import measure_color
from vision.caps import make_color_masks

TRUE = {"red": (2, 200, 200), "blue": (108, 200, 180), "purple": (150, 110, 170)}   # hue, saturation, brightness
CENTERS = {"red": (100, 150), "blue": (300, 150), "purple": (500, 150)}

def picture():
    rng = np.random.default_rng(1)
    img = np.zeros((300, 600, 3), np.uint8)
    img[:] = cv2.cvtColor(np.uint8([[[0, 0, 30]]]), cv2.COLOR_HSV2BGR)[0, 0]       # black tray
    for name, (x, y) in CENTERS.items():
        h, s, v = TRUE[name]
        patch = np.zeros((60, 60, 3), np.uint8)
        patch[..., 0] = np.clip(h + rng.integers(-3, 4, (60, 60)), 0, 179)
        patch[..., 1] = np.clip(s + rng.integers(-15, 16, (60, 60)), 0, 255)
        patch[..., 2] = np.clip(v + rng.integers(-15, 16, (60, 60)), 0, 255)
        img[y - 30:y + 30, x - 30:x + 30] = cv2.cvtColor(patch, cv2.COLOR_HSV2BGR)
    return img

def clicks(name):
    x, y = CENTERS[name]
    return [(x + dx, y + dy) for dx, dy in ((0, 0), (10, 5), (-10, 8), (5, -10))]

def test_measured_ranges_find_the_caps():
    img = picture()
    ranges = {name: measure_color(img, clicks(name)) for name in CENTERS}
    masks, _, _ = make_color_masks(img, 70, 45, color_ranges=ranges)
    for name, (x, y) in CENTERS.items():
        assert masks[name][y - 30:y + 30, x - 30:x + 30].mean() > 0.95 * 255   # its own cap
        assert masks[name][:40, :40].max() == 0                                # the tray
        for other, (ox, oy) in CENTERS.items():
            if other != name:
                assert masks[name][oy - 30:oy + 30, ox - 30:ox + 30].max() == 0

def test_red_wraps_around():
    img = picture()
    assert len(measure_color(img, clicks("red"))["hue"]) == 2                  # [0, 9] and [176, 179]
```

</details>


<details>
<summary><b>Why is this needed?</b> (click to open)</summary>

Each color is a range of numbers that we typed in by looking at a few screenshots. The camera changes its colors with the light, so caps drift out of their range: a cap is missed, or gets the wrong color, or glare looks like a cap.

![Cap colors were set by eye](images/limits/limit-2-problem.gif)

A real case: a red cap labeled purple, and glare in the corner of the cap picture.

![A red cap labeled purple](images/findings/10-red-purple-before.png)

- Hand-set rules today: red needs colorfulness 150 or more; strongly colored shades 165-176 also count as red; a cap must be 45 brighter than the tray; objects at the edge of the tray picture are ignored.
- The purple cap was measured in other light. The blue cap's brightness was never measured.
- Red sits at both ends of the shade scale (near 0 and near 179). Code help step 2 shows how to handle that.

</details>

---

## Task 3: Save every cap to a log file

![Task 3: save cap detections](images/tasks/task-3.gif)

**Your goal:** after a run, the file `logs/run.jsonl` has one line for every cap found, always with the same names.

**What you need:** Python and this repo for steps 1-6. No camera. For step 7: the camera.

**What works today:** without windows, the program already prints one line per frame, and you can save it: `python vision/tray_object_pipeline.py --camera-index 0 --no-gui > logs/run.jsonl`. This task makes it one line per cap, and works with the windows open too.

**What a line looks like:**

```json
{"frame": 1042, "time_ms": 1730000123456, "color": "red", "u": 0.412, "v": 0.688, "center_x": 206.0, "center_y": 151.4, "box": [190, 135, 32, 33], "area": 780}
```

| Name | What it means | Example |
| --- | --- | --- |
| `frame` | Which camera picture the cap was found in | `1042` |
| `time_ms` | When that picture was taken (milliseconds) | `1730000123456` |
| `color` | `"red"`, `"blue"`, `"purple"`, or `"unknown"` | `"red"` |
| `u`, `v` | Where the cap is on the tray (0 to 1) | `0.412`, `0.688` |
| `center_x`, `center_y` | The cap's middle, in pixels | `206.0`, `151.4` |
| `box` | The box around the cap: x, y, width, height in pixels | `[190, 135, 32, 33]` |
| `area` | How big the cap looks, in pixels | `780` |

**Steps:**
1. **Make your branch** `task3-records`.
2. **Add the test.** Create `tests/test_records.py` with the test in Code help. Run it: it fails.
3. **Write `make_record(frame, time_ms, obj)`** in a new file `vision/records.py`. `obj` is one cap from `result.objects`. It returns a dict with exactly the names in the table above. If the color isn't red, blue or purple, use `"unknown"`.
4. **Write `write_log(record, path)`.** It adds the record as **one line** at the **end** of the file, and never erases old lines.
5. **Run all tests:** `python -m pytest tests/`. Everything passes.
6. **Add `--log-file`** to `main()` in `vision/tray_object_pipeline.py`. In every frame, call `make_record` and `write_log` once for **each** cap in `result.objects`. Add `logs/` to `.gitignore`.
7. **Try it.** Run 1 minute with the windows open: `python vision/tray_object_pipeline.py --camera-index 0 --log-file logs/run.jsonl`. Open the file and compare it with what was printed.
8. **Push.**

**You're done when:**

| Check | How to check | Pass |
| --- | --- | --- |
| Code works | `python -m pytest tests/` | All tests pass |
| Records | The test in `tests/test_records.py`: write 3 records, read them back | 3 lines, each with exactly the names in the table |
| Unknown color | Same test, with a green cap | Saved as `"unknown"` |
| Real run | Step 7 | A line for every cap, matching what was printed |

**How to push:**
```
git add vision/records.py vision/tray_object_pipeline.py tests/test_records.py .gitignore
git commit -m "Task 3: records + log"
git push -u origin task3-records
```

<details>
<summary><b>Code help</b> (click to open)</summary>

**File:** `vision/records.py`
```python
COLORS = ("red", "blue", "purple")

def make_record(frame, time_ms, obj):
    """obj = one cap from the pipeline → the card (a dict). Other color → "unknown"."""

def write_log(record, path="logs/detections.jsonl"):
    """Add the card as one line at the end of the file."""
```

**Steps:**
1. `make_record`: build the dict with exactly these names: `frame, time_ms, color, u, v, center_x, center_y, box, area`.
   - Round `u` and `v` to 3 decimals, and `center_x` and `center_y` to 1 decimal (`round(value, 3)`).
   - Make `box` a list of ints: `[int(n) for n in obj["box"]]`. JSON has no tuples.
   - For `color`, use `obj["color"] if obj["color"] in COLORS else "unknown"`.
2. `write_log`:
   - Make the folder if it is missing (`os.makedirs(folder, exist_ok=True)`).
   - Open the file with `open(path, "a")`. The `"a"` means **append**: new text goes at the end, and old lines stay.
   - Write `json.dumps(record) + "\n"`. `json.dumps` turns the dict into text, and `"\n"` ends the line.

**Test:** `tests/test_records.py`
```python
import json
from vision.records import make_record, write_log

FIELDS = {"frame", "time_ms", "color", "u", "v", "center_x", "center_y", "box", "area"}

def fake_cap(color="red"):
    return {"color": color, "u": 0.412, "v": 0.688, "center_x": 206.0,
            "center_y": 151.4, "box": (190, 135, 32, 33), "area": 780.0}

def fake(i, color="red"):
    return make_record(i, 1730000000000 + i * 33, fake_cap(color))

def test_log_lines(tmp_path):
    path = tmp_path / "log.jsonl"
    for i in range(3):
        write_log(fake(i), path)
    lines = path.read_text().splitlines()
    assert len(lines) == 3
    assert all(set(json.loads(line)) == FIELDS for line in lines)

def test_unknown_color():
    assert fake(0, "green")["color"] == "unknown"
```

</details>


<details>
<summary><b>Why is this needed?</b> (click to open)</summary>

With the windows open, the program prints the caps once per second, and the lines scroll away. After a run we can't look back, or compare the camera's positions with a ruler. A log file keeps every cap, with fixed names, so code, tests and people all read it the same way.

![Detections are not saved](images/limits/limit-3-problem.gif)

</details>
