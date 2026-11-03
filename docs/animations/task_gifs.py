"""Short 3Blue1Brown-style GIFs that explain each task in task_delegation.md.

    python docs/animations/task_gifs.py            # render all 5 GIFs
    python docs/animations/task_gifs.py 2 4        # only tasks 2 and 4

Needs Manim CE, LaTeX and FFmpeg. GIFs go to docs/images/tasks/task-N.gif.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from manim import (
    BLACK, DOWN, LEFT, ORIGIN, RIGHT, UL, UP, WHITE, Arrow, Circle, Create,
    CurvedArrow, DashedVMobject, Dot, FadeIn, FadeOut, Flash, GrowArrow,
    Indicate, Line, MathTex, Polygon, Rectangle, RoundedRectangle, Scene,
    Square, SurroundingRectangle, Tex, Text, Transform, VGroup, Write,
    LaggedStart, ReplacementTransform, Uncreate,
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


# ---------------------------------------------------------------- Task 1

def checkerboard(cols=8, rows=6, size=0.55):
    squares = VGroup()
    for r in range(rows):
        for c in range(cols):
            sq = Square(size, stroke_color=WHITE, stroke_width=1.5)
            sq.set_fill(WHITE if (r + c) % 2 == 0 else BLACK, opacity=1)
            sq.move_to([(c - (cols - 1) / 2) * size, ((rows - 1) / 2 - r) * size, 0])
            sq.insert_n_curves(12)
            squares.add(sq)
    return squares


def barrel(p, k=0.028):
    x, y = p[0], p[1]
    r2 = x * x + y * y
    return np.array([x * (1 - k * r2), y * (1 - k * r2), 0])


class Task1Lens(TaskScene):
    title = "Task 1: Fix camera distortion"

    def construct(self):
        straight = checkerboard().shift(UP * 0.4)
        bent = straight.copy().apply_function(lambda p: barrel(p - UP * 0.4) + UP * 0.4)

        self.say("The camera lens **bends** the picture", FadeIn(bent))
        top = bent[:8]
        ruler = Line(top[0].get_corner(UL), top[7].get_corner(UP + RIGHT), color=YELLOW, stroke_width=4)
        self.say("Straight lines look **curved**, most at the **edges**", Create(ruler))
        self.play(FadeOut(ruler))

        corners = VGroup(*(Dot(barrel(np.array([(c - 3) * 0.55, (2 - r) * 0.55, 0])) + UP * 0.4,
                               radius=0.06, color=RED)
                           for r in range(5) for c in range(7)))
        self.say("Step 1: find the board's **inside corners**",
                 LaggedStart(*(FadeIn(d, scale=0.5) for d in corners), lag_ratio=0.03))

        numbers = VGroup(label("lens numbers", 28, BLUE),
                         MathTex(r"K,\ \text{dist}", font_size=40, color=BLUE)).arrange(DOWN, buff=0.15)
        box = SurroundingRectangle(numbers, color=BLUE, buff=0.25, corner_radius=0.1)
        numbers_box = VGroup(box, numbers).to_edge(RIGHT, buff=0.6).shift(UP * 0.4)
        self.say("We know they should be on **straight** lines")
        self.say("OpenCV compares $\\to$ __lens numbers__ (saved once)",
                 bent.animate.shift(LEFT * 1.6), corners.animate.shift(LEFT * 1.6), FadeIn(numbers_box))

        self.say("Then **every** picture gets straightened",
                 Transform(bent, straight.copy().shift(LEFT * 1.6)), FadeOut(corners), run_time=2.0)
        check = label("error $<$ 1 pixel", 32, GREEN).next_to(numbers_box, DOWN, buff=0.4)
        self.say("Works when: error **under 1 pixel**", Write(check))


# ---------------------------------------------------------------- Task 2

class Task2Records(TaskScene):
    title = "Task 2: Save cap detections"

    def construct(self):
        screen = Rectangle(width=4.6, height=2.6, color=GREY).move_to([-3.8, 0.6, 0])
        lines = VGroup(*(mono(f"red cap at 0.6{i}, 0.3{i}", 20, GREY) for i in range(4))).arrange(DOWN, buff=0.15)
        lines.move_to(screen)
        self.say("Today: positions only **printed** on screen, then gone", Create(screen), FadeIn(lines))
        self.play(FadeOut(lines, shift=UP * 0.5), run_time=1)

        cap = Dot([-3.8, 0.6, 0], radius=0.25, color=RED)
        fields = ['"frame": 1042', '"slot": "B3"', '"color": "red"',
                  '"x_mm": 212.4', '"y_mm": -38.0', '"z_mm": 96.0', '"time_ms": ...']
        card_text = VGroup(*(mono(f, 20) for f in fields)).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
        card_box = SurroundingRectangle(card_text, color=BLUE, buff=0.25, corner_radius=0.1)
        card = VGroup(card_box, card_text).move_to([1.0, 0.6, 0])
        arrow = Arrow(cap.get_right(), card.get_left(), color=WHITE, buff=0.2)
        self.say("Each cap $\\to$ one **record**, always the **same names**",
                 FadeOut(screen), FadeIn(cap), GrowArrow(arrow), FadeIn(card))

        log_box = Rectangle(width=3.4, height=3.2, color=TEAL).move_to([4.9, 0.6, 0])
        log_l = label("log file", 26, TEAL).next_to(log_box, UP, buff=0.15)
        self.play(Create(log_box), Write(log_l))
        rows = VGroup()
        for i in range(3):
            row = mono('{"frame": %d, ...}' % (1042 + i), 18, TEAL)
            row.move_to(log_box.get_top() + DOWN * (0.4 + 0.4 * i))
            rows.add(row)
        self.say("Every record $\\to$ **one line** in the log",
                 ReplacementTransform(card.copy(), rows[0]), run_time=1.0)
        self.play(FadeIn(rows[1], shift=DOWN * 0.2), run_time=0.5)
        self.play(FadeIn(rows[2], shift=DOWN * 0.2), run_time=0.5)

        green = Dot([-3.8, 0.6, 0], radius=0.25, color=GREEN)
        unknown = mono('"color": "unknown"', 17, YELLOW).move_to(card_text[2], aligned_edge=LEFT)
        self.say("Not red, blue or purple $\\to$ **unknown**: robot skips it",
                 ReplacementTransform(cap, green), Transform(card_text[2], unknown))


# ---------------------------------------------------------------- Task 3

class Task3PositionTest(TaskScene):
    title = "Task 3: Check cap positions"

    def construct(self):
        names = ["cap pixel", "millimeters", "slot", "record (Task 2)"]
        boxes = VGroup()
        for n in names:
            t = label(n, 26)
            boxes.add(VGroup(SurroundingRectangle(t, color=BLUE, buff=0.18, corner_radius=0.08), t))
        boxes.arrange(RIGHT, buff=0.7).move_to([0, 2.4, 0])
        arrows = VGroup(*(Arrow(a.get_right(), b.get_left(), buff=0.08, color=WHITE)
                          for a, b in zip(boxes, boxes[1:])))
        self.say("Each piece works alone. **Together?**",
                 LaggedStart(*(FadeIn(b) for b in boxes), lag_ratio=0.3), FadeIn(arrows), run_time=1.5)

        header = ["slot", "camera", "ruler", "error", ""]
        data = [("A1", "200.4, -49.8", "200, -50", "0.4 mm"),
                ("A6", "199.7, 50.3", "200, 50", "0.4 mm"),
                ("D1", "260.6, -50.1", "260, -50", "0.6 mm"),
                ("D6", "259.8, 49.5", "260, 50", "0.5 mm")]
        xs = [-4.6, -2.6, 0.0, 2.2, 3.8]

        def row(cells, y, color=WHITE):
            return VGroup(*(mono(c, 22, color).move_to([x, y, 0]) for c, x in zip(cells, xs)))

        head = row(header, 1.1, GREY)
        rows = [row(d, 0.5 - 0.55 * i) for i, d in enumerate(data)]
        self.say("Caps in **known slots**, measured with a ruler", FadeIn(head))
        marks = []
        for r in rows:
            ok = mono("pass", 22, GREEN).move_to([xs[4], r.get_y(), 0])
            marks.append(ok)
            self.play(FadeIn(r), FadeIn(ok), run_time=0.4)
        self.say("Each cap close enough? ++pass++")

        bad = row(("A6", "199.7, 60.3", "200, 50", "10.3 mm"), rows[1].get_y(), RED)
        fail = mono("FAIL", 22, RED).move_to(marks[1])
        self.say("Test the test: 1 cap 10 mm off must !!fail!!",
                 Transform(rows[1], bad), Transform(marks[1], fail))
        self.play(Indicate(rows[1], color=RED))
        self.say("All pass with the real camera $\\to$ **Limitation 1 done**",
                 Transform(rows[1], row(data[1], rows[1].get_y())),
                 Transform(marks[1], mono("pass", 22, GREEN).move_to(marks[1])))


# ---------------------------------------------------------------- Task 4

class Task4OutlineCheck(TaskScene):
    title = "Task 4: Check the tray outline"

    def construct(self):
        good = [np.array(p) for p in ([-3, -1.2, 0], [3, -1.2, 0], [3, 1.8, 0], [-3, 1.8, 0])]
        tray = Polygon(*good, stroke_width=0, fill_color="#1c1c1c", fill_opacity=1)
        last = Polygon(*good, color=BLUE, stroke_width=4)
        last_l = label("last good outline", 26, BLUE).next_to(last, UP, buff=0.15)
        self.add(tray)
        self.say("Remember the **last good** outline", Create(last), Write(last_l))

        def outline(points, color=YELLOW):
            return Polygon(*points, color=color, stroke_width=4)

        verdict = None

        def show(word, color):
            nonlocal verdict
            v = label(word, 40, color).move_to([4.9, 0.3, 0])
            if verdict is None:
                self.play(Write(v), run_time=0.5)
            else:
                self.play(ReplacementTransform(verdict, v), run_time=0.5)
            verdict = v

        new = outline([p + np.array([0.06, -0.04, 0]) for p in good])
        self.say("New outline, corners moved a little $\\to$ ++same++", Create(new))
        show("same", GREEN)
        self.wait(0.5)

        shift = np.array([0.8, -0.3, 0])
        moved = outline([p + shift for p in good])
        self.say("All 4 corners moved together $\\to$ **moved**: warn",
                 tray.animate.shift(shift), Transform(new, moved))
        show("moved", YELLOW)
        self.wait(0.5)
        self.play(tray.animate.shift(-shift), Transform(new, outline(good)), run_time=0.8)

        blob = Circle(0.6, stroke_width=0, fill_color="#262626", fill_opacity=1).move_to(good[2])
        bent_pts = [good[0], good[1], good[2] + np.array([0.5, 0.45, 0]), good[3]]
        self.say("Dark blob on a corner pulls it out", FadeIn(blob))
        self.play(Transform(new, outline(bent_pts, RED)))
        show("bent", RED)
        self.say("!!Bent!!: ignore it, keep the **last good** one",
                 Indicate(last, color=BLUE), FadeOut(new))
        self.play(FadeOut(blob))

        wobble = [outline([p + np.array([dx, dy, 0]) for p in good])
                  for dx, dy in ((0.3, 0.1), (-0.25, -0.15), (0.2, -0.2), (-0.3, 0.15))]
        new = wobble[0]
        self.say("Outline keeps jumping (something moving) $\\to$ **wait**", Create(new))
        for w in wobble[1:]:
            self.play(Transform(new, w), run_time=0.35)
        show("wait", YELLOW)
        self.wait(1)


# ---------------------------------------------------------------- Task 5

BASE = np.array([0.0, 3.3, 0])


def arm_to(tip, l1=2.6, l2=2.6, color=GREY):
    """Two-segment arm from BASE to tip (simple 2-joint math)."""
    tip = np.array(tip, dtype=float)
    d = tip - BASE
    dist = min(np.linalg.norm(d), l1 + l2 - 1e-3)
    a = np.arctan2(d[1], d[0])
    b = np.arccos((l1 ** 2 + dist ** 2 - l2 ** 2) / (2 * l1 * dist))
    elbow = BASE + l1 * np.array([np.cos(a + b), np.sin(a + b), 0])
    return VGroup(Line(BASE, elbow, color=color, stroke_width=14),
                  Line(elbow, tip, color=color, stroke_width=10),
                  Dot(BASE, radius=0.2, color=color), Dot(elbow, radius=0.12, color=color),
                  Dot(tip, radius=0.14, color=WHITE))


class Task5PickLoop(TaskScene):
    title = "Task 5: Run the pick cycle"

    def construct(self):
        tray_pts = [[-3, -2.0, 0], [3, -2.0, 0], [3, 1.0, 0], [-3, 1.0, 0]]
        tray = Polygon(*tray_pts, stroke_width=0, fill_color="#1c1c1c", fill_opacity=1)
        outline = Polygon(*tray_pts, color=GREEN, stroke_width=4)
        caps = VGroup(Dot([-1.2, -0.6, 0], radius=0.22, color=RED),
                      Dot([0.9, -1.1, 0], radius=0.22, color=BLUE))
        bin_red = Rectangle(width=1.3, height=0.9, color=RED).move_to([5.3, -1.3, 0])
        bin_l = label("red bin", 22, RED).next_to(bin_red, DOWN, buff=0.1)
        self.add(tray, caps, bin_red, bin_l)

        arm = arm_to([0.6, 0.6, 0])
        bad = Polygon([-3, -2.0, 0], [3, -2.0, 0], [3, 1.0, 0], [1.2, 1.0, 0], [0.6, 0.2, 0], [-3, 1.0, 0],
                      color=RED, stroke_width=4)
        self.add(arm)
        self.say("The arm is **in the picture**: tray outline breaks", Create(bad))
        self.play(FadeOut(bad))

        park = [5.0, 2.0, 0]
        self.say("So first: **park** the arm out of view", Transform(arm, arm_to(park)), run_time=1.5)

        flash = Rectangle(width=14.5, height=8.5, stroke_width=0, fill_color=WHITE, fill_opacity=0.5)
        self.say("Then take the **picture** and check the tray (Task 4)", FadeIn(flash), run_time=0.15)
        self.play(FadeOut(flash), Create(outline), run_time=0.6)
        ok = label("same", 30, GREEN).next_to(outline, UP, buff=0.1).shift(LEFT * 2.2)
        self.play(Write(ok))

        target = caps[0].get_center()
        self.say("Move, **pick**, drop in the bin", Transform(arm, arm_to(target)), run_time=1.3)
        self.play(Transform(arm, arm_to(bin_red.get_center() + UP * 0.3)),
                  caps[0].animate.move_to(bin_red.get_center()), run_time=1.3)

        self.say("Back to park, then **repeat**", Transform(arm, arm_to(park)),
                 FadeOut(outline), FadeOut(ok), run_time=1.3)

        steps = ["park", "picture", "check", "pick"]
        pos = [np.array([5.0 + 1.1 * np.cos(t), -0.9 + 0.9 * np.sin(t), 0])
               for t in (np.pi / 2, 0, -np.pi / 2, np.pi)]
        loop = VGroup(*(label(s, 24, YELLOW).move_to(p) for s, p in zip(steps, pos)))
        arcs = VGroup(*(CurvedArrow(pos[i] + (pos[(i + 1) % 4] - pos[i]) * 0.3,
                                    pos[(i + 1) % 4] - (pos[(i + 1) % 4] - pos[i]) * 0.3,
                                    angle=-np.pi / 3, color=GREY, stroke_width=2)
                        for i in range(4)))
        self.play(FadeOut(bin_red), FadeOut(bin_l), FadeOut(caps[0]), FadeIn(loop), FadeIn(arcs))
        self.play(LaggedStart(*(Indicate(s, color=WHITE) for s in loop), lag_ratio=0.5), run_time=2)

        bent = Polygon([-3, -2.0, 0], [3, -2.0, 0], [3, 0.2, 0], [2.4, 0.4, 0], [-3, 1.0, 0],
                       color=RED, stroke_width=4)
        self.say("Arm still over a corner $\\to$ !!bent!!: no pick, wait",
                 Transform(arm, arm_to([2.7, 0.8, 0])), run_time=1.2)
        self.play(Create(bent), Indicate(loop[2], color=RED), loop[3].animate.set_opacity(0.3))
        self.wait(1.2)


SCENES = {1: Task1Lens, 2: Task2Records, 3: Task3PositionTest,
          4: Task4OutlineCheck, 5: Task5PickLoop}


def render(number, width=800, fps=12):
    scene = SCENES[number].__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / f"task-{number}.gif"
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(f"{gif}  {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or SCENES:
        render(n)
