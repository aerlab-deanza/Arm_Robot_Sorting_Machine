"""Short 3Blue1Brown-style GIFs that explain each task in task_delegation.md.

    python docs/animations/task_gifs.py            # render all 3 GIFs
    python docs/animations/task_gifs.py 2 4        # only tasks 2 and 4

Needs Manim CE, LaTeX and FFmpeg. GIFs go to docs/images/tasks/task-N.gif.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from manim import (
    BLACK, DOWN, LEFT, ORIGIN, RIGHT, UL, UP, WHITE, Arrow, Circle, Create,
    DashedVMobject, DecimalNumber, Dot, FadeIn, FadeOut, Flash, GrowArrow,
    Indicate, Line, MathTex, Polygon, Rectangle, RoundedRectangle, Scene,
    SurroundingRectangle, Tex, Text, Transform, VGroup, VMobject, ValueTracker,
    Write, LaggedStart, ReplacementTransform, always_redraw,
)

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "tasks"

# 3b1b palette
BLUE = "#58C4DD"
TEAL = "#5CD0B3"
YELLOW = "#FFFF00"
RED = "#FC6255"
GREEN = "#83C167"
GREY = "#888888"
DARK = "#333333"
PURPLE = "#B07CE8"
DARK_BLUE = "#3B7BEA"
CYAN = "#00FFFF"
TRAY = "#1C1C1C"
MONO = "Consolas"

MARKS = {"**": YELLOW, "__": BLUE, "!!": RED, "++": GREEN}


def rich(markup, size=34, max_width=13.0):
    """Tex from light markup: **yellow**, __blue__, !!red!!, ++green++."""
    tokens, i = [], 0
    while i < len(markup):
        for mark, color in MARKS.items():
            if markup.startswith(mark, i):
                j = markup.index(mark, i + 2)
                tokens.append((markup[i + 2:j], color))
                i = j + 2
                break
        else:
            hits = [k for k in (markup.find(m, i) for m in MARKS) if k >= 0]
            j = min(hits) if hits else len(markup)
            tokens.append((markup[i:j], WHITE))
            i = j
    tex = Tex(*(t for t, _ in tokens), font_size=size, arg_separator="")
    for part, (_, color) in zip(tex, tokens):
        part.set_color(color)
    if tex.width > max_width:
        tex.scale_to_fit_width(max_width)
    return tex


def label(text, size=28, color=WHITE):
    return Tex(text, font_size=size, color=color)


def mono(text, size=22, color=WHITE):
    return Text(text, font=MONO, font_size=size, color=color)


class TaskScene(Scene):
    title = ""

    def setup(self):
        self.camera.background_color = BLACK
        self.caption = None
        if self.title:
            self.add(label(self.title, 26, GREY).to_corner(UL, buff=0.35))

    def say(self, markup, *animations, run_time=1.2, hold=None):
        """Show a caption, play the animations, then hold long enough to read."""
        text = rich(markup).to_edge(DOWN, buff=0.4)
        if self.caption is not None:
            self.play(FadeOut(self.caption, shift=UP * 0.15), run_time=0.3)
        self.play(Write(text), run_time=min(0.4 + 0.025 * len(markup), 1.2))
        self.caption = text
        if animations:
            self.play(*animations, run_time=run_time)
        self.wait(hold if hold is not None else 0.4 + len(markup.split()) / 3.2)


def polyline(points, closed=True, **kwargs):
    mob = VMobject(**kwargs)
    pts = list(points) + ([points[0]] if closed else [])
    mob.set_points_as_corners(pts)
    return mob


QUAD = np.array([[-3.0, 1.5, 0], [2.4, 1.7, 0], [3.5, -1.2, 0], [-3.8, -1.0, 0]]) + UP * 0.4


# ---------------------------------------------------------------- Task 1

class Task1Corners(TaskScene):
    title = "Task 1: Keep the four main corners"

    def construct(self):
        tray = polyline(QUAD, stroke_width=0).set_fill(WHITE, 1)
        spike = Rectangle(width=0.14, height=1.3, stroke_width=0).set_fill(WHITE, 1).move_to([0.0, 2.6, 0])
        tip = np.array([0.0, 3.25, 0])
        window = label("Tray threshold", 24, GREY).to_corner(UL, buff=0.35).shift(DOWN * 0.7)
        order = [QUAD[0], tip, QUAD[1], QUAD[2], QUAD[3]]
        dots = VGroup(*(Dot(p, color=YELLOW if i != 1 else RED, radius=0.1) for i, p in enumerate(order)))
        self.say("The outline has **five** corners. One is the cable's tip",
                 FadeIn(window), FadeIn(tray), FadeIn(spike), LaggedStart(*(FadeIn(d, scale=2) for d in dots), lag_ratio=0.2),
                 run_time=1.2)

        small = polyline([QUAD[0], tip, QUAD[1]], stroke_width=0).set_fill(RED, 0.55)
        big = polyline([QUAD[1], QUAD[2], QUAD[3]], stroke_width=0).set_fill(TEAL, 0.4)
        small_l = label("small", 26, RED).move_to([0.0, 2.55, 0]).shift(RIGHT * 1.3 + UP * 0.45)
        big_l = label("big", 26, TEAL).move_to([0.6, 0.2, 0])
        self.say("Each corner makes a **triangle** with its two neighbors",
                 FadeIn(small), FadeIn(small_l), FadeIn(big), FadeIn(big_l), run_time=1.0)

        self.say("Remove the corner with the **smallest** triangle",
                 FadeOut(small), FadeOut(small_l), FadeOut(big), FadeOut(big_l), FadeOut(dots[1]),
                 FadeOut(spike), run_time=1.0)
        outline = polyline(QUAD, color=GREEN, stroke_width=5)
        self.say("The **four real corners** stay, and the outline hugs the tray",
                 Create(outline), hold=1.8)


# ---------------------------------------------------------------- Task 2

class Task2Colors(TaskScene):
    title = "Task 2: Calibrate the cap colors"

    def construct(self):
        tray = Rectangle(width=6.0, height=3.2, stroke_color=GREY, stroke_width=2).set_fill(TRAY, 1).move_to([-3.4, 0.5, 0])
        caps = {"red": Circle(0.38, stroke_width=0).set_fill(RED, 1).move_to([-5.0, 0.9, 0]),
                "blue": Circle(0.38, stroke_width=0).set_fill(DARK_BLUE, 1).move_to([-3.4, -0.3, 0]),
                "purple": Circle(0.38, stroke_width=0).set_fill(PURPLE, 1).move_to([-1.8, 1.0, 0])}
        self.say("Show the straightened tray with the **real caps**",
                 FadeIn(tray), *(FadeIn(c) for c in caps.values()), run_time=0.8)

        plane = VGroup(Line([1.0, -1.8, 0], [6.4, -1.8, 0], color=GREY), Line([1.0, -1.8, 0], [1.0, 2.2, 0], color=GREY))
        plane_x = label("hue", 24, GREY).next_to(plane[0], DOWN, buff=0.1)
        plane_y = label("saturation", 24, GREY).next_to(plane[1], UP, buff=0.1).shift(RIGHT * 0.5)
        self.play(FadeIn(plane), FadeIn(plane_x), FadeIn(plane_y), run_time=0.6)

        rng = np.random.default_rng(2)
        spots = {"red": (1.3, 1.5), "blue": (3.9, 1.45), "purple": (5.2, 0.5)}   # where each cap's pixels land
        colors = {"red": RED, "blue": DARK_BLUE, "purple": PURPLE}
        boxes = VGroup()
        for i, name in enumerate(("red", "blue", "purple")):
            cap = caps[name]
            clicks = VGroup(*(Dot(cap.get_center() + np.array([dx, dy, 0]), radius=0.07, color=YELLOW)
                              for dx, dy in ((0, 0), (0.18, 0.1), (-0.15, 0.12), (0.05, -0.2))))
            cx, cy = spots[name]
            cloud = VGroup(*(Dot([cx + rng.normal(0, 0.12), cy + rng.normal(0, 0.18), 0], radius=0.05, color=colors[name])
                             for _ in range(14)))
            box = SurroundingRectangle(cloud, color=YELLOW, buff=0.1, stroke_width=3)
            text = "Click on a cap: its pixels land in the **hue-saturation** plane" if i == 0 else None
            if text:
                self.say(text, LaggedStart(*(FadeIn(c, scale=2) for c in clicks), lag_ratio=0.2),
                         LaggedStart(*(FadeIn(d) for d in cloud), lag_ratio=0.04), run_time=1.4, hold=0.2)
                self.say("A box around the cloud is the **range** for that color", Create(box), run_time=0.8)
            else:
                self.play(LaggedStart(*(FadeIn(c, scale=2) for c in clicks), lag_ratio=0.15),
                          LaggedStart(*(FadeIn(d) for d in cloud), lag_ratio=0.03), Create(box), run_time=1.4)
            boxes.add(box)

        card = VGroup(Rectangle(width=3.0, height=0.9, color=BLUE, stroke_width=3), mono("colors.json", 22, BLUE))
        card[1].move_to(card[0])
        card.move_to([4.6, 2.9, 0])
        self.say("Save the ranges in a file. The pipeline **loads it** at start-up",
                 FadeIn(card, shift=DOWN * 0.2), run_time=0.8)

        masks = VGroup(*(Circle(0.38, stroke_width=0).set_fill(WHITE, 1).move_to(c.get_center()) for c in caps.values()))
        self.say("Every cap is found. Nothing else is", Transform(tray, tray.copy().set_fill(BLACK)),
                 *(Transform(c, m) for c, m in zip(caps.values(), masks)), run_time=1.0, hold=1.6)


# ---------------------------------------------------------------- Task 3

class Task3Records(TaskScene):
    title = "Task 3: Save cap detections"

    def construct(self):
        # The camera picture with two caps.
        tray = Rectangle(width=4.4, height=2.3, stroke_color=GREY, stroke_width=2).set_fill(TRAY, 1).move_to([-4.3, 2.0, 0])
        tray_label = label("camera picture of the tray", 22, GREY).next_to(tray, DOWN, buff=0.1)
        red = Circle(0.3, stroke_width=0).set_fill(RED, 1).move_to([-5.2, 2.2, 0])
        blue = Circle(0.3, stroke_width=0).set_fill(DARK_BLUE, 1).move_to([-3.4, 1.7, 0])
        self.say("The program finds the caps in the camera picture",
                 FadeIn(tray), FadeIn(tray_label), FadeIn(red), FadeIn(blue), run_time=0.8, hold=0.2)
        found = SurroundingRectangle(red, color=GREEN, buff=0.1, stroke_width=4)
        self.play(Create(found), run_time=0.5)

        # One record = one card with the facts about one cap.
        facts = (("frame", "1042", "(which picture)"), ("color", '"red"', "(which color)"),
                 ("u", "0.412", "(how far across)"), ("v", "0.688", "(how far down)"))
        names, values, hints = VGroup(), VGroup(), VGroup()
        for i, (n, v, h) in enumerate(facts):
            y = -0.5 * i
            names.add(mono(n, 22, BLUE).move_to([0.0, y, 0], aligned_edge=LEFT))
            values.add(mono(v, 22, WHITE).move_to([1.5, y, 0], aligned_edge=LEFT))
            hints.add(mono(h, 16, GREY).move_to([2.9, y, 0], aligned_edge=LEFT))
        table = VGroup(names, values, hints)
        card = VGroup(SurroundingRectangle(table, color=BLUE, buff=0.25, corner_radius=0.1), table)
        card.move_to([2.3, 1.9, 0])
        card_label = label("a record", 24, BLUE).next_to(card, UP, buff=0.12)
        arrow = Arrow(tray.get_right() + RIGHT * 0.1, card.get_left(), color=WHITE, buff=0.15)
        self.say("It writes the facts about **one** cap on a **record**, like a card",
                 GrowArrow(arrow), FadeIn(card), FadeIn(card_label), run_time=1.2)
        self.say("Every record uses the **same names**", Indicate(names, color=YELLOW), hold=0.8)

        # The record becomes one line of text.
        line_text = '{"frame": 1042, "color": "red", "u": 0.412, "v": 0.688, ...}'
        line = mono(line_text, 17, TEAL).move_to([0.0, -0.55, 0])
        self.say("A record is written as **one line** of text",
                 ReplacementTransform(card.copy(), line), FadeOut(arrow), run_time=1.3)

        # The log file: a notebook where lines are only added at the end.
        log_box = Rectangle(width=11.6, height=2.0, color=TEAL, stroke_width=3).move_to([0.0, -2.0, 0])
        log_label = label("the log file: lines are only added at the end", 22, TEAL).next_to(log_box, UP, buff=0.1).align_to(log_box, LEFT)
        row_y = [-1.4, -1.78, -2.16, -2.54]

        def row(text, y):
            return mono(text, 16, TEAL).move_to([-5.5, y, 0], aligned_edge=LEFT)

        row0 = row(line_text, row_y[0])
        self.say("The line is **added** to the log file",
                 Create(log_box), FadeIn(log_label), Transform(line, row0), FadeOut(card), FadeOut(card_label),
                 run_time=1.2)

        row1 = row('{"frame": 1042, "color": "blue", "u": 0.571, "v": 0.402, ...}', row_y[1])
        row2 = row('{"frame": 1043, "color": "red", "u": 0.413, "v": 0.688, ...}', row_y[2])
        self.say("Next cap, next picture: **one more line** each time",
                 FadeOut(found), FadeIn(row1, shift=DOWN * 0.15), run_time=0.8, hold=0.3)
        self.play(FadeIn(row2, shift=DOWN * 0.15), run_time=0.6)
        self.say("Later, open the file to **replay** the run or compare it with a ruler",
                 Indicate(VGroup(line, row1, row2), color=YELLOW), hold=0.8)

        # A cap that is not red, blue or purple.
        green = Circle(0.3, stroke_width=0).set_fill(GREEN, 1).move_to(blue)
        row3 = row('{"frame": 1043, "color": "unknown", "u": 0.571, "v": 0.402, ...}', row_y[3])
        self.say("Not red, blue or purple? It is saved as **unknown**, never thrown away",
                 Transform(blue, green), FadeIn(row3, shift=DOWN * 0.15), run_time=1.0, hold=0.3)
        self.play(Indicate(row3, color=YELLOW), run_time=0.8)
        self.wait(1.2)


SCENES = {1: Task1Corners, 2: Task2Colors, 3: Task3Records}


def render(number, width=800, fps=12):
    scene = SCENES[number].__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / f"task-{number}.gif"
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(f"{gif}  {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or SCENES:
        render(n)
