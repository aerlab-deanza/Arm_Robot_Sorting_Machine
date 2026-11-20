"""Render the arm vision explainer as short GIFs, one per part of docs/arm_vision.md.

    python docs/animations/arm_vision_video/render_gifs.py              # all GIFs
    python docs/animations/arm_vision_video/render_gifs.py S09 S10      # only scenes whose name starts with these

GIFs cannot be paused, so each one covers one small idea (about 20-50 seconds). A scene is cut
into several GIFs at its `self.next_section(...)` calls (see scenes_2.py and scenes_3.py).

Needs Manim CE, LaTeX (MiKTeX) and FFmpeg. Output: docs/images/arm_vision/*.gif.
Render cache: docs/animations/arm_vision_video/media/ (ignored by git).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "images" / "arm_vision"

# (script, scene, [GIF names, one per section in order]). Names match the parts of docs/arm_vision.md.
SCENES = [
    ("scenes_1.py", "S01Question", ["01-question"]),
    ("scenes_1.py", "S02RealPicture", ["02-real-picture"]),
    ("scenes_1.py", "S03Curve", ["03-curve"]),
    ("scenes_1.py", "S04Tendon", ["04-tendon"]),
    ("scenes_1.py", "S05Gravity", ["05-gravity"]),
    ("scenes_2.py", "S06Research", ["06-research"]),
    ("scenes_2.py", "S06bWhichModel", ["07-which-model"]),
    ("scenes_2.py", "S07Overview", ["08-overview"]),
    ("scenes_2.py", "S08bBiggestBlob", ["09-biggest-blob"]),
    ("scenes_2.py", "S08Segmentation", ["10a-dark-pixels", "10b-thick-shapes", "10c-clip-gaps"]),
    ("scenes_2.py", "S09Skeleton", ["11a-skeleton", "11b-shadows-and-ends"]),
    ("scenes_3.py", "S10Fit", ["12a-fit-bowl", "12b-flexible-curve"]),
    ("scenes_3.py", "S11Coordinates", ["13-coordinates"]),
    ("scenes_3.py", "S12Smoothing", ["14-steady"]),
    ("scenes_3.py", "S13Results", ["15a-measured", "15b-not-proven", "15c-check-by-hand"]),
    ("scenes_3.py", "S14Recap", ["16-recap"]),
]


def to_gif(mp4, gif, width=800, fps=10):
    """Small GIF: few colors, only changed pixels stored."""
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=48:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)


def main():
    """Render the chosen scenes with sections, then turn each section into a GIF."""
    wanted = sys.argv[1:]
    media = HERE / "media"
    OUT.mkdir(parents=True, exist_ok=True)
    for script, scene, names in SCENES:
        if wanted and not any(scene.startswith(w) for w in wanted):
            continue
        subprocess.run([sys.executable, "-m", "manim", "render", "-r", "960,540", "--fps", "12",
                        "--save_sections", "--media_dir", str(media), "--disable_caching", script, scene],
                       cwd=HERE, check=True)
        sections = sorted(media.glob(f"videos/{Path(script).stem}/540p12/sections/{scene}_*.mp4"))
        if len(sections) != len(names):
            sys.exit(f"{scene}: found {len(sections)} sections, expected {len(names)}: {[s.name for s in sections]}")
        for mp4, name in zip(sections, names):
            gif = OUT / f"{name}.gif"
            to_gif(mp4, gif)
            print(f"{gif.name}  {gif.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
