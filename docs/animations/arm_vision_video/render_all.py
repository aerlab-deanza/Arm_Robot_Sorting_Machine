"""Render every scene at 1080p and join them into one MP4.

    python docs/animations/arm_vision_video/render_all.py            # final: 1920x1080, 30 fps
    python docs/animations/arm_vision_video/render_all.py --draft    # quick check: 854x480, 15 fps

Needs Manim CE, LaTeX (MiKTeX) and FFmpeg. Output: docs/arm_vision_explained.mp4
(the draft goes to docs/arm_vision_explained_draft.mp4). Render cache: docs/animations/arm_vision_video/media/ (ignored by git).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENES = [
    ("scenes_1.py", "S01Question"), ("scenes_1.py", "S02RealPicture"), ("scenes_1.py", "S03Curve"),
    ("scenes_1.py", "S04Tendon"), ("scenes_1.py", "S05Gravity"), ("scenes_2.py", "S06Research"),
    ("scenes_2.py", "S06bWhichModel"), ("scenes_2.py", "S07Overview"), ("scenes_2.py", "S08bBiggestBlob"),
    ("scenes_2.py", "S08Segmentation"), ("scenes_2.py", "S09Skeleton"), ("scenes_3.py", "S10Fit"),
    ("scenes_3.py", "S11Coordinates"), ("scenes_3.py", "S12Smoothing"), ("scenes_3.py", "S13Results"),
    ("scenes_3.py", "S14Recap"),
]


def main():
    """Render all scenes, then join them with FFmpeg."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", action="store_true", help="small and fast, to check pacing")
    parser.add_argument("--only", help="render only scenes whose name contains this text")
    args = parser.parse_args()
    width, height, fps = (854, 480, 15) if args.draft else (1920, 1080, 30)
    media = HERE / "media"
    folder = media / "videos"
    clips = []
    for script, scene in SCENES:
        if args.only and args.only not in scene:
            continue
        subprocess.run([sys.executable, "-m", "manim", "render", "-r", f"{width},{height}", "--fps", str(fps),
                        "--media_dir", str(media), script, scene], cwd=HERE, check=True)
        clips.append(next(folder.rglob(f"{height}p{fps}/{scene}.mp4")))
    listing = HERE / "media" / "clips.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    name = "arm_vision_explained_draft.mp4" if args.draft else "arm_vision_explained.mp4"
    out = HERE.parents[1] / name
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)], check=True)
    print("written", out)


if __name__ == "__main__":
    main()
