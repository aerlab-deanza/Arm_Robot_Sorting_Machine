"""3Blue1Brown-style GIFs that show each problem in limitation.md.

    python docs/animations/limit_gifs.py          # render all 4 GIFs
    python docs/animations/limit_gifs.py 2 4      # only limits 2 and 4

Needs Manim CE, LaTeX and FFmpeg. GIFs go to docs/images/limits/limit-N-problem.gif.
"""
import colorsys
import subprocess
import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, UL, WHITE, Arrow, Circle, Create, DashedVMobject, Dot,
    FadeIn, FadeOut, Flash, Indicate, Line, Polygon, Rectangle, Square, Transform,
    VGroup, VMobject, Write, LaggedStart,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_gifs  # noqa: E402
from task_gifs import BLUE, DARK, GREEN, GREY, RED, YELLOW, TEAL, label, mono  # noqa: E402
from pipeline_gifs import FastScene, PURPLE, DARK_BLUE, CYAN, TRAY  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "limits"

QUAD = np.array([[-3.0, 1.5, 0], [2.4, 1.7, 0], [3.5, -1.2, 0], [-3.8, -1.0, 0]]) + UP * 0.4


def polyline(points, closed=True, **kwargs):
    mob = VMobject(**kwargs)
    pts = list(points) + ([points[0]] if closed else [])
    mob.set_points_as_corners(pts)
    return mob


# ----------------------------------------------------------------- limit 1

class Limit1Spike(FastScene):
    title = "Limit 1: a thin object"

    def construct(self):
        tray = polyline(QUAD, stroke_width=0).set_fill(WHITE, 1)
        spike = Rectangle(width=0.14, height=1.3, stroke_width=0).set_fill(WHITE, 1)
        spike.move_to([0.0, 2.6, 0])        # its foot sits inside the tray's top edge
        window = label("Tray threshold", 24, GREY).to_corner(UL, buff=0.35).shift(DOWN * 0.7)
        self.say("A thin dark **cable** touches the tray",
                 FadeIn(window), FadeIn(tray), FadeIn(spike), run_time=0.8)

        dots = VGroup(*(Dot(p, color=YELLOW, radius=0.1) for p in QUAD))
        tip = Dot(spike.get_top(), color=RED, radius=0.12)
        self.say("The outline gets **five corners**, not four",
                 LaggedStart(*(FadeIn(d, scale=2) for d in dots), FadeIn(tip, scale=2), lag_ratio=0.2),
                 run_time=1.2)

        outline = polyline(QUAD, color=GREEN, stroke_width=5)
        bounding = polyline([np.array([-3.8, 2.7, 0]), np.array([3.5, 2.7, 0]),
                             np.array([3.5, -1.2, 0]), np.array([-3.8, -1.2, 0])],
                            color=RED, stroke_width=5)
        self.play(Create(outline), run_time=0.6)
        self.say("The four-corner check fails: a **bigger rectangle** is used instead",
                 Transform(outline, bounding), FadeOut(dots), FadeOut(tip), run_time=1.3)

        locked = label("TRAY LOCKED", 28, CYAN).to_corner(UL, buff=0.35).shift(DOWN * 1.3)
        self.say("It locks like this, and **stays wrong** for the whole run",
                 outline.animate.set_color(CYAN), FadeIn(locked), run_time=0.8, hold=1.8)


# ----------------------------------------------------------------- limit 2

class Limit2Colors(FastScene):
    title = "Limit 2: colors set by eye"

    def construct(self):
        def x_of(hue):
            return -5.8 + 11.6 * hue / 179

        bar = VGroup(*(Rectangle(width=11.6 / 60 + 0.01, height=0.5, stroke_width=0).set_fill(
            "#%02X%02X%02X" % tuple(int(c * 255) for c in colorsys.hsv_to_rgb(i * 3 * 2 / 360, 0.9, 0.9)), 1)
            .move_to([x_of(i * 3 + 1.5), -0.6, 0]) for i in range(60)))
        axis_l = label("hue", 24, GREY).next_to(bar, DOWN, buff=0.15)
        self.say("Each color has a **range** of hue, set by eye", FadeIn(bar), FadeIn(axis_l), run_time=0.8, hold=0.1)

        def band(first, last, color):
            return Line([x_of(first), -1.2, 0], [x_of(last), -1.2, 0], color=color, stroke_width=9)

        bands = VGroup(band(0, 10, RED), band(177, 179, RED), band(100, 124, DARK_BLUE), band(125, 176, PURPLE))
        self.play(LaggedStart(*(Create(b) for b in bands), lag_ratio=0.25), run_time=1.2)

        rng = np.random.default_rng(4)
        samples = []
        for lo, hi, color, first, last in ((0, 14, RED, 0, 10), (96, 120, DARK_BLUE, 100, 124),
                                           (124, 164, PURPLE, 125, 176)):
            for h in rng.integers(lo, hi + 1, 7):
                samples.append((int(h), color, first <= h <= last))
        dots = VGroup(*(Dot([x_of(h), 0.4 + 0.18 * (i % 4), 0], radius=0.08, color=c)
                        for i, (h, c, ok) in enumerate(samples)))
        self.say("Real caps are measured here", LaggedStart(*(FadeIn(d, scale=2) for d in dots), lag_ratio=0.05),
                 run_time=1.2, hold=0.2)
        crosses = VGroup(*(label(r"$\times$", 30, YELLOW).move_to(d.get_center() + UP * 0.3)
                           for d, (h, c, ok) in zip(dots, samples) if not ok))
        self.say("A cap outside its range is **missed**", FadeIn(crosses), run_time=0.8, hold=1.0)
        self.say("Lights change: **more** misses",
                 dots.animate.shift(RIGHT * 0.35), crosses.animate.shift(RIGHT * 0.35), run_time=1.0, hold=1.8)


# ----------------------------------------------------------------- limit 3

class Limit3Height(FastScene):
    title = "Limit 3: a cap above the tray"

    def construct(self):
        floor_y = -1.9
        tray = Line([-5.5, floor_y, 0], [5.5, floor_y, 0], color=GREY, stroke_width=6)
        tray_l = label("tray surface", 24, GREY).next_to(tray, DOWN, buff=0.15).align_to(tray, LEFT)
        camera = Rectangle(width=0.9, height=0.5, color=BLUE, stroke_width=3).move_to([0.0, 3.2, 0])
        camera_l = label("camera, looking straight down", 24, BLUE).next_to(camera, RIGHT, buff=0.2)

        def tube_with_cap(x):
            tube = Rectangle(width=0.5, height=1.7, stroke_width=0).set_fill(DARK, 1).move_to([x, floor_y + 0.85, 0])
            cap = Rectangle(width=0.7, height=0.25, stroke_width=0).set_fill(RED, 1).move_to([x, floor_y + 1.82, 0])
            return VGroup(tube, cap)

        far = tube_with_cap(3.2)
        self.say("Our caps sit on tubes, **above** the tray",
                 Create(tray), FadeIn(tray_l), FadeIn(far), FadeIn(camera), FadeIn(camera_l), run_time=1.0)

        cap_top = np.array([3.2, floor_y + 1.82, 0])
        cam_pt = np.array([0.0, 3.0, 0])
        direction = (cap_top - cam_pt) / np.linalg.norm(cap_top - cam_pt)
        t_floor = (floor_y - cam_pt[1]) / direction[1]
        seen = cam_pt + direction * t_floor
        ray = Line(cam_pt, cap_top, color=YELLOW, stroke_width=3)
        ray_on = DashedVMobject(Line(cap_top, seen, color=YELLOW, stroke_width=3))
        self.say("The camera sees the cap along a **ray**", Create(ray), run_time=0.9, hold=0.2)
        real = Dot([3.2, floor_y, 0], color=GREEN, radius=0.12)
        seen_dot = Dot(seen, color=RED, radius=0.12)
        real_l = label("really here", 24, GREEN).next_to(real, DOWN, buff=0.45).shift(LEFT * 0.7)
        seen_l = label("measured here", 24, RED).next_to(seen_dot, DOWN, buff=0.45).shift(RIGHT * 0.2)
        self.say("Straightening puts every point **on the tray surface**",
                 Create(ray_on), FadeIn(real), FadeIn(seen_dot), FadeIn(real_l), FadeIn(seen_l), run_time=1.2)

        near = tube_with_cap(0.9)
        near_top = np.array([0.9, floor_y + 1.82, 0])
        d2 = (near_top - cam_pt) / np.linalg.norm(near_top - cam_pt)
        seen2 = cam_pt + d2 * ((floor_y - cam_pt[1]) / d2[1])
        ray2 = Line(cam_pt, near_top, color=YELLOW, stroke_width=3)
        ray2_on = DashedVMobject(Line(near_top, seen2, color=YELLOW, stroke_width=3))
        dots2 = VGroup(Dot([0.9, floor_y, 0], color=GREEN, radius=0.1), Dot(seen2, color=RED, radius=0.1))
        self.say("Near the middle the error is **small**. Near the edges it is **big**",
                 FadeIn(near), Create(ray2), Create(ray2_on), FadeIn(dots2), run_time=1.3, hold=1.8)


# ----------------------------------------------------------------- limit 4

class Limit4Records(FastScene):
    title = "Limit 4: nothing is saved"

    def construct(self):
        screen = Rectangle(width=6.4, height=3.4, color=GREY).move_to([-2.6, 0.5, 0])
        self.add(screen)
        lines = []
        self.say("Caps are **printed** on the screen, once per second", hold=0.1)
        for i in range(9):
            line = mono('red  (0.41, 0.69)' if i % 2 == 0 else 'blue (0.58, 0.50)', 22, GREY)
            line.move_to(screen.get_bottom() + UP * 0.4)
            line.align_to(screen, LEFT).shift(RIGHT * 0.4)
            moves = [FadeIn(line, shift=UP * 0.2)] + [l.animate.shift(UP * 0.5) for l in lines]
            lines.append(line)
            if len(lines) > 5:
                moves.append(FadeOut(lines.pop(0)))      # the oldest line scrolls away for good
            self.play(*moves, run_time=0.35)
        folder = Rectangle(width=2.6, height=1.8, color=GREY, stroke_width=3).move_to([4.2, 0.5, 0])
        question = label("log file?", 30, YELLOW).move_to(folder)
        self.say("Older lines scroll away. **Nothing is saved**",
                 FadeIn(folder), FadeIn(question), run_time=0.8)
        self.say("We can't replay a run or **compare it** with a ruler", Indicate(question, color=YELLOW), hold=1.8)


SCENES = {1: Limit1Spike, 2: Limit2Colors, 3: Limit3Height, 4: Limit4Records}


def render(number, width=800, fps=12):
    scene = SCENES[number].__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / f"limit-{number}-problem.gif"
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(f"{gif}  {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or SCENES:
        render(n)
