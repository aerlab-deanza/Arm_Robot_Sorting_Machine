# Agent Guide

Instructions for AI coding agents working in this repository.

## Project

A robot arm that sorts test-tube caps by color. A camera looks at a black tray, the PC finds the tray and the colored caps, and (later) the arm picks each cap and drops it in a bin.

- **Works today:** find the tray, find orange / blue / purple caps, report positions as fractions of the tray.
- **Not yet:** pixel → arm millimeters, saved records, arm control. See [docs/limitation.md](docs/limitation.md).
- **Team:** about 5 beginners. Write code, docs, and messages for them.

## Layout

| Path | What |
| --- | --- |
| `vision/tray_object_pipeline.py` | The vision pipeline (OpenCV). Runs on the PC. |
| `firmware/TrayObjectDetection/` | AMB82-Mini camera sketch (Arduino, Realtek AmebaNN). Streams RTSP. |
| `docs/computer_vision_pipeline.md` | How the pipeline works, step by step, with GIFs. |
| `docs/documentation.md` | Findings and why the setup was chosen. |
| `docs/limitation.md` | What's missing before automatic picking. Setup rules for the demo. |
| `docs/task_delegation.md` | 5 tasks for the team: what to build, fake data, tests, how to push. |
| `docs/animations/task_gifs.py` | Makes the task GIFs (Manim). |
| `docs/images/` | Screenshots; `limits/`, `pipeline/`, `tasks/` hold the GIFs the docs embed. |
| `tests/` | Doesn't exist yet. Planned in `task_delegation.md`. |

## Run

```powershell
python -m pip install -r requirements.txt
python vision/tray_object_pipeline.py --camera-index 0      # USB camera
python vision/tray_object_pipeline.py --camera-index 1      # laptop camera
python vision/tray_object_pipeline.py --url rtsp://192.168.0.25:554   # AMB82-Mini (default)
python -m pytest tests/                                     # once tests exist; run from repo root
```

- Windows, PowerShell. Python 3.13.
- The camera and arm aren't always connected. Don't assume hardware is there. Test with fake data or drawn pictures instead.
- `tray_object_pipeline.py` can be imported safely (`from vision.tray_object_pipeline import tray_quad`). Its `main()` only runs as a script.

## Pipeline facts (keep docs in sync if you change these)

- **Tray:** dark pixels, `V ≤ 85`, `S ≤ 130`, any hue. `MORPH_CLOSE` kernel 9 × 2. Rejects shapes touching the image border. Aspect 1.2–8, rectangularity ≥ 0.48, `approxPolyDP` 0.04, `minAreaRect` fallback when rectangularity ≥ 0.58.
- **Tracker** (`TrayQuadTracker`): blend 0.28, keep the last outline for 8 frames, a big jump needs 3 agreeing frames. 2 s settle after the first detection.
- **Colors:** orange hue 8–24, blue 88–124 (light and dark blue), purple 125–165. `V ≥ 45` for all colors. `S ≥ 70` for orange and purple; blue uses `S ≥ 50` (`BLUE_MIN_SATURATION`) because light blue is pale. Red is not detected. Skin is hue 16–23 on our camera, so hands in the tray show up as orange. Caps with colors near a range edge (brown, pale purple) break into specks; use strongly colored caps.
- **Objects:** min side 12 px, aspect ≤ 1.9. Duplicate if IoU ≥ 0.30 or overlap ≥ 0.75 of the smaller box.
- **Object tracker** (`ObjectTracker`): matches same-color objects within 0.08 of the tray size between frames. Shows an object once seen in 3 of the last 5 frames; reports the median of its last 5 boxes and centers. Reset when the tray is lost. Drawn boxes and the printout use tracked objects; the mask window is raw.
- **Ask before changing color ranges.** Prefer avoiding false caps over catching every cap.

The planned functions and file names for new code are in `docs/task_delegation.md`. Use those names (`undistort`, `make_record`, `write_log`, `check_outline`, `is_still`, `run`, …) so the team's pieces fit together.

## Writing docs

- **Plain, short, beginner language.** Short sentences. Grammar can be sacrificed for clarity. No jargon without a one-line explanation.
- Tasks in `task_delegation.md` use the Q&A layout: *What's wrong now? → What's the idea? → What do I build? → Do I need another task first? → How do I test without hardware? → How do I know it works? → How do I push? → What changes with real hardware?* Code goes in a folded `<details>` "Code help" block.
- Link limitations with anchors, e.g. `limitation.md#1-the-robot-cant-use-the-cameras-positions-yet`.
- Embed GIFs with relative paths (`images/tasks/task-1.gif`). They play on GitHub. MP4 files don't play in Markdown.

## Animations (GIFs)

- Style: **3Blue1Brown.** Pure black background, LaTeX text, saturated colors (blue `#58C4DD`, teal `#5CD0B3`, yellow `#FFFF00` for the key word, red `#FC6255`, green `#83C167`), objects morph instead of slide-show cuts.
- **Text on screen, no voice-over.** Each step has one short caption at the bottom.
- Make them: `python docs/animations/task_gifs.py` (all) or `python docs/animations/task_gifs.py 3`. Needs Manim CE, LaTeX (MiKTeX), FFmpeg. Output: `docs/images/tasks/task-N.gif`, 800 px wide, 12 fps.
- After rendering, look at a few frames before saying it's done.
- Keep GIFs small (aim for ≤ 2 MB each). The source scripts for `limits/` and `pipeline/` GIFs were in a local `video/` folder that no longer exists.

## Git

- `main` is the shared branch. Teammates work on task branches (`task1-lens`, …).
- **Only commit or push when the user asks.** Never `--force` push.
- **Never commit generated files:** `docs/animations/media/` (Manim render cache, hundreds of MP4s), `__pycache__/`, `*.pyc`, `.claude/`, logs. Check `.gitignore` before `git add .`.
- Upload speed is slow (~80 KB/s): big pushes time out with `HTTP 408`. Keep commits small. `http.postBuffer` is already raised for this repo.
- `phong_local_notes` is private and ignored.

## Safety

- Anything that moves the real arm needs a person watching with the emergency stop in reach. Don't write code that moves the arm without a park / stop path.
- Don't change camera IPs, Wi-Fi settings, or firmware without asking.
