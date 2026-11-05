"""3Blue1Brown-style GIF of the whole vision pipeline, start to finish.

    python docs/animations/pipeline_recap.py

Needs Manim CE, LaTeX and FFmpeg. Output: docs/images/pipeline/09a-recap.gif.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from manim import (
    BLACK, DOWN, LEFT, RIGHT, UL, UP, WHITE, Circle, Create, DashedVMobject, Dot,
    FadeIn, FadeOut, Indicate, LaggedStart, Line, MathTex, Polygon, Rectangle,
    Square, SurroundingRectangle, Transform, VGroup, Write, AnimationGroup,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_gifs  # noqa: E402  (shared 3b1b look: captions, colors, fonts)
from task_gifs import BLUE, GREEN, GREY, RED, YELLOW, TaskScene, label, rich  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "pipeline" / "09a-recap.gif"

PURPLE = "#B07CE8"
DARK_BLUE = "#3B7BEA"  # the pipeline detects dark blue only
TABLE = "#B9A47C"
TRAY = "#1C1C1C"
CYAN = "#00FFFF"  # the locked outline is cyan in the program
task_gifs.MARKS.update({"%%": PURPLE, "@@": DARK_BLUE})

# The tray as the camera sees it: a skewed four-sided shape.
QUAD = np.array([[-3.3, 1.55, 0], [2.7, 1.75, 0], [3.9, -1.25, 0], [-4.2, -1.05, 0]])
# The same tray after straightening.
RECT = np.array([[-4.2, 1.75, 0], [4.2, 1.75, 0], [4.2, -1.75, 0], [-4.2, -1.75, 0]])
# Caps as (color name, color, u, v): u across, v down, both 0 to 1.
CAPS = [("red", RED, 0.22, 0.38), ("blue", DARK_BLUE, 0.55, 0.68), ("purple", PURPLE, 0.8, 0.3)]


def on_quad(corners, u, v):
    """Point at (u, v) inside a four-corner shape (TL, TR, BR, BL)."""
    tl, tr, br, bl = corners
    top = tl + (tr - tl) * u
    bottom = bl + (br - bl) * u
    return top + (bottom - top) * v


def shifted(corners, rng, amount):
    return corners + np.array([[*rng.normal(0, amount, 2), 0] for _ in range(4)])


class PipelineRecap(TaskScene):
    title = "The whole pipeline"

    def setup(self):
        super().setup()
        self.caption = None

    def say(self, markup, *animations, run_time=1.0, hold=None):
        """Faster than the task GIFs' captions: this GIF has many steps."""
        text = rich(markup).to_edge(DOWN, buff=0.4)
        swap = [FadeOut(self.caption, shift=UP * 0.15)] if self.caption is not None else []
        self.play(*swap, FadeIn(text, shift=UP * 0.15), run_time=0.45)
        self.caption = text
        if animations:
            self.play(*animations, run_time=run_time)
        self.wait(hold if hold is not None else 0.25 + len(markup.split()) / 5)

    def construct(self):
        up = UP * 0.55
        table = Rectangle(width=11.2, height=4.9, stroke_color=GREY, stroke_width=2)
        table.set_fill(TABLE, 1).shift(up)
        tray = Polygon(*QUAD, stroke_width=0).set_fill(TRAY, 1).shift(up)
        caps = VGroup(*(Circle(0.3, stroke_width=0).set_fill(c, 1).move_to(on_quad(QUAD, u, v) + up)
                        for _, c, u, v in CAPS))
        caps[0].stretch(0.8, 1)
        caps[1].stretch(0.8, 1)
        caps[2].stretch(0.8, 1)

        # 1. Pixels
        self.say("A camera picture: a grid of **pixels**",
                 FadeIn(table), FadeIn(tray), FadeIn(caps), run_time=1.0)
        grid = VGroup(*(Line([x, -1.85, 0], [x, 2.75, 0], stroke_width=0.6, color=GREY)
                        for x in np.arange(-5.2, 5.25, 0.4)),
                      *(Line([-5.2, y, 0], [5.2, y, 0], stroke_width=0.6, color=GREY)
                        for y in np.arange(-1.85, 2.8, 0.4)))
        pixel = Square(0.4, color=YELLOW, stroke_width=4).move_to(caps[0])
        hsv = MathTex(r"(H, S, V) = (3,\ 210,\ 220)", font_size=34, color=YELLOW)
        hsv.next_to(pixel, UP, buff=0.25)
        self.play(FadeIn(grid, run_time=0.8))
        self.say("Each pixel: **three numbers** (color, strength, brightness)",
                 Create(pixel), Write(hsv), run_time=1.0)
        self.play(FadeOut(grid), FadeOut(pixel), FadeOut(hsv), run_time=0.6)

        # 2. Dark-pixel threshold
        self.say("Keep the **dark** pixels: that's the tray",
                 table.animate.set_fill(BLACK), tray.animate.set_fill(WHITE),
                 caps.animate.set_fill(BLACK), run_time=1.4)

        # 3. Outline and corners
        outline = Polygon(*QUAD, color=GREEN, stroke_width=5).shift(up)
        corners = VGroup(*(Dot(p + up, color=YELLOW, radius=0.1) for p in QUAD))
        self.say("Trace its outline, find **4 corners**", Create(outline), run_time=1.2)
        self.play(LaggedStart(*(FadeIn(d, scale=2) for d in corners), lag_ratio=0.3), run_time=0.9)

        # 4. Steady outline
        rng = np.random.default_rng(3)
        self.say("Corners **jitter** from frame to frame", hold=0.1)
        for _ in range(3):
            jitter = shifted(QUAD, rng, 0.12)
            self.play(Transform(outline, Polygon(*jitter, color=GREEN, stroke_width=5).shift(up)),
                      *(d.animate.move_to(p + up) for d, p in zip(corners, jitter)), run_time=0.22)
        self.say("Blend with earlier frames: the outline **stays steady**",
                 Transform(outline, Polygon(*QUAD, color=GREEN, stroke_width=5).shift(up)),
                 *(d.animate.move_to(p + up) for d, p in zip(corners, QUAD)), run_time=1.0)

        self.say("Still for 0.75 s: the outline **locks** (cyan)",
                 outline.animate.set_color(CYAN), run_time=0.8, hold=0.4)

        # 5. Mask: keep only the tray
        self.say("Fill the outline, keep **only the tray**",
                 tray.animate.set_fill(TRAY),
                 *(c.animate.set_fill(col) for c, (_, col, _, _) in zip(caps, CAPS)),
                 run_time=1.2)

        # 6. Straighten
        rect_caps = [on_quad(RECT, u, v) + up for _, _, u, v in CAPS]
        self.say("**Straighten** the tray into a rectangle",
                 FadeOut(table),
                 Transform(tray, Polygon(*RECT, stroke_width=0).set_fill(TRAY, 1).shift(up)),
                 Transform(outline, Polygon(*RECT, color=CYAN, stroke_width=5).shift(up)),
                 *(d.animate.move_to(p + up) for d, p in zip(corners, RECT)),
                 *(c.animate.move_to(p).stretch_to_fit_height(0.6) for c, p in zip(caps, rect_caps)),
                 run_time=1.6)
        self.play(FadeOut(corners), outline.animate.set_stroke(GREY, 2), run_time=0.5)

        # Too-bright tray: darken it before looking for colors.
        self.say("Tray too bright? **Darken** it first",
                 tray.animate.set_fill("#5A5A5A"), run_time=0.6, hold=0.1)
        self.play(tray.animate.set_fill(TRAY), run_time=0.8)

        # 7. Color masks
        names = VGroup(*(label(n, 30, col).next_to(c, DOWN, buff=0.18)
                         for c, (n, col, _, _) in zip(caps, CAPS)))
        self.say("Find !!red!!, @@dark blue@@ and %%purple%% pixels",
                 LaggedStart(*(Indicate(c, color=WHITE, scale_factor=1.3) for c in caps), lag_ratio=0.3),
                 FadeIn(names), run_time=1.2, hold=0.3)
        white = caps.copy().set_fill(WHITE)
        self.play(tray.animate.set_fill(BLACK), Transform(caps, white), run_time=0.8)
        self.wait(0.5)
        self.play(tray.animate.set_fill(TRAY),
                  *(c.animate.set_fill(col) for c, (_, col, _, _) in zip(caps, CAPS)), run_time=0.8)

        # 8. Boxes and centers
        boxes = VGroup(*(SurroundingRectangle(c, color=GREEN, buff=0.12, stroke_width=4) for c in caps))
        dots = VGroup(*(Dot(c.get_center(), color=WHITE, radius=0.08) for c in caps))
        self.say("Box each cap, mark its **center**",
                 FadeOut(names), LaggedStart(*(Create(b) for b in boxes), lag_ratio=0.25),
                 FadeIn(dots), run_time=1.3)

        # 9. Object tracker
        blue_box = boxes[1]
        ticks = VGroup(*(label(s, 30, GREEN if s == r"\checkmark" else RED)
                         for s in (r"\checkmark", r"\checkmark", r"$\times$", r"\checkmark", r"\checkmark")))
        ticks.scale(1.4).arrange(RIGHT, buff=0.45)
        ticks.next_to(RECT[2] + up, DOWN, buff=0.25).set_x(blue_box.get_x())
        frames = label("last 5 frames", 26, GREY).next_to(ticks, RIGHT, buff=0.35)
        self.say("A frame misses the cap? Its box **stays**",
                 LaggedStart(*(FadeIn(t) for t in ticks), lag_ratio=0.25), FadeIn(frames), run_time=1.2)
        ghost = DashedVMobject(blue_box.copy().set_color(RED))
        self.play(FadeIn(ghost), Indicate(ticks[2], color=RED), run_time=0.6)
        self.play(FadeOut(ghost), run_time=0.4)
        self.say("Shown once seen in **3 of the last 5** frames", Indicate(blue_box, color=GREEN), run_time=0.8)
        self.play(FadeOut(ticks), FadeOut(frames), run_time=0.5)

        # 10. Report positions
        zero = MathTex("0", font_size=30, color=GREY).next_to(RECT[0] + up, UL, buff=0.08)
        one_u = MathTex("1", font_size=30, color=GREY).next_to(RECT[1] + up, UP, buff=0.12)
        one_v = MathTex("1", font_size=30, color=GREY).next_to(RECT[3] + up, LEFT, buff=0.12)
        u_axis = Line(RECT[0] + up + UP * 0.12, RECT[1] + up + UP * 0.12, color=GREY, stroke_width=2)
        v_axis = Line(RECT[0] + up + LEFT * 0.12, RECT[3] + up + LEFT * 0.12, color=GREY, stroke_width=2)
        _, col, u, v = CAPS[0]
        where = MathTex(rf"(u, v) = ({u:.2f},\ {v:.2f})", font_size=34, color=RED)
        where.next_to(boxes[0], RIGHT, buff=0.25)
        self.say("Report each center as a **fraction** of the tray",
                 Create(u_axis), Create(v_axis), FadeIn(zero), FadeIn(one_u), FadeIn(one_v),
                 Write(where), run_time=1.3)

        self.say("Pixels $\\to$ simple steps $\\to$ **color and position**",
                 Indicate(where, color=YELLOW), run_time=1.0, hold=2.5)


def render(width=800, fps=12):
    scene = PipelineRecap.__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(OUT)], check=True)
    print(f"{OUT}  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    render()
