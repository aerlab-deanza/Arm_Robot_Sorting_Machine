"""3Blue1Brown-style GIFs for steps of the vision pipeline that changed.

    python docs/animations/pipeline_gifs.py            # render all
    python docs/animations/pipeline_gifs.py hsv lock   # only these

Names: hsv, steady, lock, cleanup, tracker.
Needs Manim CE, LaTeX and FFmpeg. GIFs go to docs/images/pipeline/.
The numbers on screen match vision/tray_object_pipeline.py. If you change
a default there, change it here too.
"""
import colorsys
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UL, UP, WHITE, AnnularSector, Arc, Circle, Create,
    DashedVMobject, Dot, FadeIn, FadeOut, Indicate, LaggedStart, Line, MathTex,
    Polygon, Rectangle, RoundedRectangle, Square, SurroundingRectangle,
    Transform, VGroup, VMobject, Write, PI,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_gifs  # noqa: E402  (shared 3b1b look: captions, colors, fonts)
from task_gifs import BLUE, GREEN, GREY, RED, YELLOW, TaskScene, label, rich  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "pipeline"

PURPLE = "#B07CE8"
DARK_BLUE = "#3B7BEA"  # the pipeline detects dark blue only
CYAN = "#00FFFF"       # the locked outline is cyan in the program
TRAY = "#1C1C1C"
SKIN = "#E0A885"
task_gifs.MARKS.update({"%%": PURPLE, "@@": DARK_BLUE})


class FastScene(TaskScene):
    """Captions a bit faster than the task GIFs: these GIFs have many steps."""

    def setup(self):
        super().setup()
        self.caption = None

    def say(self, markup, *animations, run_time=1.0, hold=None):
        text = rich(markup).to_edge(DOWN, buff=0.4)
        swap = [FadeOut(self.caption, shift=UP * 0.15)] if self.caption is not None else []
        self.play(*swap, FadeIn(text, shift=UP * 0.15), run_time=0.45)
        self.caption = text
        if animations:
            self.play(*animations, run_time=run_time)
        self.wait(hold if hold is not None else 0.25 + len(markup.split()) / 4.5)


# ------------------------------------------------------------------ hsv

class HsvScene(FastScene):
    title = "Step 2: HSV and the red wrap-around"

    def construct(self):
        lit_rgb, shadow_rgb = (232, 58, 48), (112, 24, 20)

        def hsv_of(rgb):
            pixel = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
            return [int(v) for v in cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0]]

        def hexcolor(rgb):
            return "#%02X%02X%02X" % rgb

        squares, texts = [], []
        for x, name, rgb in ((-5.0, "lit", lit_rgb), (-2.6, "in shadow", shadow_rgb)):
            sq = Square(1.3, stroke_width=0).set_fill(hexcolor(rgb), 1).move_to([x, 1.1, 0])
            tag = label(name, 26, GREY).next_to(sq, UP, buff=0.2)
            nums = MathTex(rf"R\ {rgb[0]}\quad G\ {rgb[1]}\quad B\ {rgb[2]}", font_size=28)
            nums.next_to(sq, DOWN, buff=0.25)
            squares.append(VGroup(sq, tag))
            texts.append(nums)

        self.say("The camera stores each pixel as **R, G, B**",
                 FadeIn(squares[0]), FadeIn(texts[0]))
        self.say("In shadow, **all three** numbers change",
                 FadeIn(squares[1]), FadeIn(texts[1]))

        hsv_texts = []
        for sq, rgb in zip(squares, (lit_rgb, shadow_rgb)):
            h, s, v = hsv_of(rgb)
            t = VGroup(*(MathTex(rf"{k}\ {n}", font_size=28) for k, n in (("H", h), ("S", s), ("V", v))))
            t.arrange(RIGHT, buff=0.3).move_to(sq[0].get_bottom() + DOWN * 0.43)
            hsv_texts.append(t)
        self.say("HSV: **hue** = color, **saturation** = strength, **value** = brightness",
                 FadeOut(texts[0]), FadeOut(texts[1]), FadeIn(hsv_texts[0]), FadeIn(hsv_texts[1]),
                 run_time=1.0, hold=0.4)
        self.say("Shadow changes only the **value**. The hue stays",
                 Indicate(hsv_texts[0][0], color=YELLOW), Indicate(hsv_texts[1][0], color=YELLOW),
                 hold=1.0)

        self.play(*(FadeOut(m) for m in (*squares, *hsv_texts)), run_time=0.6)

        # The hue wheel. OpenCV hue 0-179 is half of the 360 degrees of a color wheel.
        center = np.array([-2.2, 0.5, 0])
        outer, inner = 1.9, 1.3
        wheel = VGroup()
        for h in range(0, 180, 3):
            r, g, b = colorsys.hsv_to_rgb(h * 2 / 360, 1, 1)
            sector = AnnularSector(inner_radius=inner, outer_radius=outer, angle=6 * PI / 180,
                                   start_angle=h * 2 * PI / 180, stroke_width=0)
            sector.set_fill("#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255)), 1)
            wheel.add(sector)
        wheel.move_to(center)
        wheel_label = label("hue: a circle", 26, GREY).next_to(wheel, DOWN, buff=0.2)
        self.say("Hue is a **circle**: red sits at both ends", FadeIn(wheel), FadeIn(wheel_label))

        def band(first, last, color):
            arc = Arc(radius=outer + 0.14, start_angle=first * 2 * PI / 180,
                      angle=(last - first + 1) * 2 * PI / 180, color=color, stroke_width=9)
            return arc.shift(center)

        bands = [(band(0, 10, RED), band(177, 179, RED)), (band(100, 124, DARK_BLUE),), (band(125, 176, PURPLE),)]
        notes = VGroup(
            label("red: 0 to 10 and 177 to 179", 28, RED),
            label("dark blue: 100 to 124", 28, DARK_BLUE),
            label("purple: 125 to 176", 28, PURPLE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.35).move_to([3.4, 1.0, 0])
        self.say("Red needs **two ranges**. Dark blue and purple sit between",
                 *(Create(a) for a in bands[0]), run_time=1.0, hold=0.2)
        self.play(FadeIn(notes[0]), run_time=0.4)
        self.play(*(Create(a) for a in bands[1]), FadeIn(notes[1]), run_time=0.8)
        self.play(*(Create(a) for a in bands[2]), FadeIn(notes[2]), run_time=0.8)
        self.wait(0.8)

        # Saturation gauge: hands are pale, the cap is strongly colored.
        gauge = Line([0.6, -1.2, 0], [6.2, -1.2, 0], color=GREY, stroke_width=3)
        scale = 5.6 / 255

        def at(s):
            return np.array([0.6 + s * scale, -1.2, 0])

        pale = Line(at(0), at(150), color=GREY, stroke_width=10)
        strong = Line(at(150), at(255), color=RED, stroke_width=10)
        ticks = VGroup(*(label(str(s), 22, GREY).next_to(at(s), DOWN, buff=0.15) for s in (0, 150, 255)))
        hand = label("hand in shadow", 24, SKIN).next_to(at(105), UP, buff=0.25)
        cap = label("red cap", 24, RED).next_to(at(240), UP, buff=0.25)
        gauge_title = label("saturation", 26, GREY).next_to(gauge, UP, buff=1.0).align_to(gauge, LEFT)
        self.say("Red also needs **strong color**: saturation at least 150",
                 FadeIn(gauge_title), Create(gauge), FadeIn(pale), FadeIn(strong), FadeIn(ticks),
                 run_time=1.0, hold=0.2)
        self.play(FadeIn(hand), FadeIn(cap), run_time=0.6)
        self.say("A shadowed hand reads red but pale. The cap does not",
                 Indicate(hand, color=YELLOW), hold=1.6)


# ---------------------------------------------------------------- steady

class SteadyScene(FastScene):
    title = "Step 4: steady the outline"

    def construct(self):
        # 1. The settle timer.
        bar_back = Rectangle(width=6.0, height=0.35, stroke_color=GREY, stroke_width=2).move_to([0, 0.6, 0])
        bar = Rectangle(width=6.0, height=0.35, stroke_width=0).set_fill(YELLOW, 1).move_to(bar_back)
        timer = label("LOCALIZE TRAY - 0.5 s", 30, YELLOW).next_to(bar_back, UP, buff=0.3)
        self.say("First sighting: wait **0.5 s** before trusting it",
                 FadeIn(bar_back), FadeIn(bar), FadeIn(timer), run_time=0.8, hold=0.1)
        self.play(bar.animate.stretch_to_fit_width(0.01).align_to(bar_back, LEFT), run_time=1.6)
        self.say("A timer, **not** a hand detector",
                 FadeOut(bar), FadeOut(bar_back), FadeOut(timer), hold=0.9)

        # 2. Simulate the smoother on one corner coordinate.
        rng = np.random.default_rng(5)
        n = 40
        truth = np.where(np.arange(n) >= 18, 1.2, 0.0)
        est = truth + rng.normal(0, 0.07, n)
        est[8] += 1.0                      # one wild frame
        missing = set(range(27, 35))       # 8 frames with no detection
        weight, confirm = 0.28, 3
        smooth, pending, pend_n, out = est[0], None, 0, []
        for i in range(n):
            if i in missing:
                out.append(smooth)
                continue
            x = est[i]
            if abs(x - smooth) > 0.5:
                if pending is not None and abs(x - pending) <= 0.2:
                    pending, pend_n = (pending + x) / 2, pend_n + 1
                else:
                    pending, pend_n = x, 1
                if pend_n >= confirm:
                    smooth, pending, pend_n = x, None, 0
            else:
                pending, pend_n = None, 0
                smooth = (1 - weight) * smooth + weight * x
            out.append(smooth)

        def pos(i, y):
            return np.array([-5.6 + 0.28 * i, -0.9 + 1.3 * y, 0])

        axis = Line(pos(-1, -0.4), pos(n, -0.4), color=GREY, stroke_width=2)
        axis_label = label("frame", 24, GREY).next_to(axis, DOWN, buff=0.15)
        y_label = label("one tray corner", 24, GREY).to_corner(UL, buff=0.35).shift(DOWN * 0.8)
        dots = [Dot(pos(i, est[i]), radius=0.055, color=YELLOW) for i in range(n) if i not in missing]
        dot_index = [i for i in range(n) if i not in missing]
        line = VMobject(color=BLUE, stroke_width=5)
        line.set_points_as_corners([pos(i, y) for i, y in enumerate(out)])

        def reveal(first, last, run_time):
            group = [d for d, i in zip(dots, dot_index) if first <= i < last]
            self.play(LaggedStart(*(FadeIn(d, scale=1.5) for d in group), lag_ratio=0.12), run_time=run_time)

        self.add(axis, axis_label, y_label)
        self.say("Each frame the tray's corners **jitter** a little", hold=0.1)
        reveal(0, 8, 1.0)
        self.say("Blend: new outline = **0.72** old + **0.28** new",
                 FadeIn(MathTex(r"c_t = 0.72\, c_{t-1} + 0.28\, x_t", font_size=34, color=BLUE)
                        .to_corner(UL, buff=0.35).shift(RIGHT * 7.0)), hold=0.4)
        part = VMobject(color=BLUE, stroke_width=5)
        part.set_points_as_corners([pos(i, y) for i, y in enumerate(out[:8])])
        self.play(Create(part), run_time=0.8)

        self.say("One **wild** frame is ignored", hold=0.1)
        reveal(8, 12, 0.6)
        ring = Circle(radius=0.22, color=YELLOW, stroke_width=3).move_to(dots[dot_index.index(8)])
        part2 = VMobject(color=BLUE, stroke_width=5)
        part2.set_points_as_corners([pos(i, y) for i, y in enumerate(out[:18])])
        self.play(Create(ring), Transform(part, part2), run_time=0.8)
        self.wait(0.5)

        self.say("A real move needs **3 agreeing** frames", hold=0.1)
        reveal(12, 27, 1.4)
        part3 = VMobject(color=BLUE, stroke_width=5)
        part3.set_points_as_corners([pos(i, y) for i, y in enumerate(out[:27])])
        self.play(Transform(part, part3), run_time=0.8)
        self.wait(0.5)

        shade = Rectangle(width=0.28 * 8, height=2.6, stroke_width=0).set_fill(RED, 0.18)
        shade.move_to([(pos(27, 0)[0] + pos(34, 0)[0]) / 2, -0.1, 0])
        gap_note = label("no detection", 24, RED).next_to(shade, UP, buff=0.1)
        self.say("Tray missed? The old outline is **kept** for 8 frames",
                 FadeIn(shade), FadeIn(gap_note), run_time=0.6, hold=0.1)
        part4 = VMobject(color=BLUE, stroke_width=5)
        part4.set_points_as_corners([pos(i, y) for i, y in enumerate(out[:35])])
        self.play(Transform(part, part4), run_time=0.8)
        reveal(35, n, 0.8)
        part5 = VMobject(color=BLUE, stroke_width=5)
        part5.set_points_as_corners([pos(i, y) for i, y in enumerate(out)])
        self.play(Transform(part, part5), run_time=0.6)
        self.wait(1.2)


# ------------------------------------------------------------------ lock

class LockScene(FastScene):
    title = "Step 4: lock the outline"

    def construct(self):
        up = UP * 0.45
        quad = np.array([[-3.0, 1.5, 0], [2.4, 1.7, 0], [3.5, -1.2, 0], [-3.8, -1.0, 0]]) + up
        tray = Polygon(*quad, stroke_width=0).set_fill(TRAY, 1)
        outline = Polygon(*quad, color=GREEN, stroke_width=5)
        status = label("FINDING TRAY", 28, GREEN).to_corner(UL, buff=0.35).shift(DOWN * 0.6)
        bar_back = Rectangle(width=3.0, height=0.22, stroke_color=GREY, stroke_width=2)
        bar_back.next_to(status, DOWN, buff=0.2).align_to(status, LEFT)
        bar = Rectangle(width=0.01, height=0.22, stroke_width=0).set_fill(GREEN, 1)
        bar.align_to(bar_back, LEFT).align_to(bar_back, UP)
        seconds = label("still for 0.75 s", 22, GREY).next_to(bar_back, DOWN, buff=0.1).align_to(bar_back, LEFT)

        self.say("Glare can still bend the outline. So we **lock** it",
                 FadeIn(tray), Create(outline), FadeIn(status), FadeIn(bar_back), FadeIn(seconds))
        full = Rectangle(width=3.0, height=0.22, stroke_width=0).set_fill(GREEN, 1)
        full.align_to(bar_back, LEFT).align_to(bar_back, UP)
        self.play(Transform(bar, full), run_time=1.4)
        locked_status = label("TRAY LOCKED (r = find again)", 28, CYAN).move_to(status, aligned_edge=LEFT)
        self.say("Still for **0.75 s**: it locks (cyan)",
                 outline.animate.set_color(CYAN), Transform(status, locked_status),
                 FadeOut(bar), FadeOut(bar_back), FadeOut(seconds), hold=0.5)

        bent = quad.copy()
        bent[1] = bent[1] + np.array([-1.3, -1.0, 0])
        bent_poly = DashedVMobject(Polygon(*bent, color=RED, stroke_width=4))
        glare = Circle(0.4, stroke_width=0).set_fill(WHITE, 0.7).move_to(quad[1] + np.array([-0.6, -0.1, 0]))
        self.say("Glare bends what the camera sees. The locked outline **ignores** it",
                 FadeIn(glare), Create(bent_poly), hold=1.2)
        self.play(FadeOut(bent_poly), FadeOut(glare), run_time=0.5)

        hand = RoundedRectangle(corner_radius=0.5, width=3.0, height=1.8).set_fill(SKIN, 1).set_stroke(width=0)
        hand.move_to([0.4, -0.1, 0] + up)
        self.say("A hand hides the tray? Still **locked**", FadeIn(hand), hold=1.0)
        self.play(FadeOut(hand), run_time=0.5)

        shift = np.array([1.5, -0.55, 0])
        new_quad = quad + shift
        ghost = DashedVMobject(Polygon(*quad, color=GREY, stroke_width=2))
        moved = Polygon(*new_quad, color=GREEN, stroke_width=4)
        self.say("The same tray **moved** and stays there for 1 s ...",
                 FadeIn(ghost), tray.animate.shift(shift), Create(moved), run_time=1.2, hold=0.2)
        timer = label("1 s", 26, YELLOW).next_to(moved, UP, buff=0.15)
        self.play(FadeIn(timer), run_time=0.4)
        self.wait(0.6)
        following = label("FINDING TRAY", 28, GREEN).move_to(status, aligned_edge=LEFT)
        self.say("... so it **unlocks** and follows the tray",
                 FadeOut(ghost), FadeOut(timer), FadeOut(outline), Transform(status, following),
                 run_time=1.0)
        relocked = label("TRAY LOCKED (r = find again)", 28, CYAN).move_to(status, aligned_edge=LEFT)
        self.say("Steady again: it **locks** in the new place",
                 moved.animate.set_color(CYAN), Transform(status, relocked), run_time=0.8)

        key = RoundedRectangle(corner_radius=0.1, width=0.8, height=0.8, color=WHITE, stroke_width=3)
        key_r = label("r", 34, WHITE).move_to(key)
        keycap = VGroup(key, key_r).to_corner(UL, buff=0.35).shift(RIGHT * 9.5 + DOWN * 0.6)
        self.say("Or press **r** to find the tray again", FadeIn(keycap), hold=1.4)


# --------------------------------------------------------------- cleanup

class CleanupScene(FastScene):
    title = "Step 7: clean the color mask"

    def construct(self):
        cell = 0.38
        raw = np.zeros((9, 16), dtype=np.uint8)
        raw[1:8, 4:13] = 1
        raw[4, 8] = 0                     # a hole inside the cap
        raw[0, 0] = raw[0, 15] = raw[8, 15] = 1   # specks
        kernel = np.ones((3, 3), np.uint8)
        # Pad with black first, so growing and shrinking at the grid edge behaves like a real picture.
        pad = 2

        def morph(op, arr):
            padded = cv2.copyMakeBorder(arr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            return op(padded, kernel)[pad:-pad, pad:-pad]

        eroded = morph(cv2.erode, raw)
        opened = morph(cv2.dilate, eroded)
        grown = morph(cv2.dilate, opened)
        closed = morph(cv2.erode, grown)

        origin = np.array([-2.85, 1.75, 0])
        cells = []
        for r in range(raw.shape[0]):
            for c in range(raw.shape[1]):
                sq = Square(cell, stroke_color="#333333", stroke_width=1)
                sq.set_fill(WHITE if raw[r, c] else "#000000", 1)
                sq.move_to(origin + np.array([c * cell, -r * cell, 0]))
                cells.append(sq)
        grid = VGroup(*cells)
        note = label("illustrative grid, 3 x 3 brush (the program uses 5 x 5)", 22, GREY)
        note.next_to(grid, DOWN, buff=0.25)

        names = VGroup(label("red", 30, RED), label("dark blue", 30, DARK_BLUE), label("purple", 30, PURPLE))
        names.arrange(RIGHT, buff=0.7).next_to(grid, UP, buff=0.3)

        def show(arr, run_time=0.9):
            self.play(*(sq.animate.set_fill(WHITE if arr[i // raw.shape[1], i % raw.shape[1]] else "#000000", 1)
                        for i, sq in enumerate(cells)), run_time=run_time)

        self.say("Keep the pixels of one color: specks and a hole remain",
                 FadeIn(grid), FadeIn(names), FadeIn(note), run_time=0.8)
        self.say("**Opening**: shrink, then grow. Specks vanish", hold=0.1)
        show(eroded)
        show(opened)
        self.wait(0.4)
        self.say("**Closing**: grow, then shrink. The hole fills", hold=0.1)
        show(grown)
        show(closed)
        self.wait(0.4)
        box = SurroundingRectangle(VGroup(*(cells[r * raw.shape[1] + c] for r in range(1, 8) for c in range(4, 13))),
                                   color=GREEN, buff=0.05, stroke_width=4)
        self.say("Brush size matters: too small or too big **both fail**. Then trace the outline",
                 Create(box), hold=1.6)


# --------------------------------------------------------------- tracker

class TrackerScene(FastScene):
    title = "Step 7: steady the cap boxes"

    def construct(self):
        window, min_hits = 5, 3
        tray = Rectangle(width=8.0, height=3.0, stroke_color=GREY, stroke_width=2).set_fill(TRAY, 1)
        tray.move_to([0, 0.6, 0])
        cap_pos = tray.get_center() + np.array([-1.2, 0.0, 0])
        speck_pos = tray.get_center() + np.array([2.3, -0.7, 0])
        cap = Circle(0.4, stroke_width=0).set_fill(RED, 1).move_to(cap_pos).stretch(0.85, 1)

        # What the detector sees each frame: (cap seen?, speck seen?).
        frames = [(1, 0), (1, 1), (1, 0), (0, 0), (1, 0), (1, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
        rng = np.random.default_rng(11)
        history = []

        slots = VGroup(*(Square(0.55, stroke_color=GREY, stroke_width=2) for _ in range(window)))
        slots.arrange(RIGHT, buff=0.15).move_to([-1.2, -2.0, 0])
        slots_label = label("cap seen? last 5 frames", 24, GREY).next_to(slots, UP, buff=0.15)
        counter = label("frame 0", 26, GREY).next_to(tray, UP, buff=0.15).align_to(tray, LEFT)
        key = VGroup(
            VGroup(Square(0.2, color=YELLOW, stroke_width=3), label("this frame", 22, GREY)).arrange(RIGHT, buff=0.15),
            VGroup(Square(0.2, color=GREEN, stroke_width=3), label("tracker", 22, GREY)).arrange(RIGHT, buff=0.15),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.12).to_corner(UL, buff=0.35).shift(DOWN * 0.8)

        self.say("Every frame is detected from scratch: boxes **jitter** and **blink**",
                 FadeIn(tray), FadeIn(cap), FadeIn(slots), FadeIn(slots_label), FadeIn(counter), FadeIn(key),
                 run_time=0.8, hold=0.2)

        steady_box = None
        marks = []
        cap_hits_text = {1: "A one-frame **speck** is not a cap",
                         2: "Shown once seen in **3 of the last 5** frames",
                         3: "A missed frame? The box **stays**"}
        for i, (cap_seen, speck_seen) in enumerate(frames):
            history.append(cap_seen)
            raw_boxes = VGroup()
            if cap_seen:
                jitter = rng.normal(0, 0.05, 2)
                box = Rectangle(width=1.0, height=0.85, color=YELLOW, stroke_width=3)
                raw_boxes.add(box.move_to(cap_pos + np.array([jitter[0], jitter[1], 0])))
            if speck_seen:
                raw_boxes.add(Rectangle(width=0.35, height=0.35, color=YELLOW, stroke_width=3).move_to(speck_pos))
            new_counter = label(f"frame {i + 1}", 26, GREY).move_to(counter, aligned_edge=LEFT)

            recent = history[-window:]
            mark = label(r"\checkmark" if cap_seen else r"$\times$", 30, GREEN if cap_seen else RED)
            marks.append(mark)
            shown = sum(recent) >= min_hits
            plays = [FadeIn(raw_boxes), Transform(counter, new_counter)]
            visible = marks[-window:]
            mark.move_to(slots[len(visible) - 1])
            plays.append(FadeIn(mark))
            if len(marks) > window:
                plays.append(FadeOut(marks[-window - 1]))
            # Older marks slide left as the window moves on.
            for slot, m in zip(slots, visible[:-1]):
                plays.append(m.animate.move_to(slot))
            if shown and steady_box is None:
                steady_box = SurroundingRectangle(cap, color=GREEN, buff=0.12, stroke_width=5)
                plays.append(Create(steady_box))
            if not shown and steady_box is not None:
                plays.append(FadeOut(steady_box))
                steady_box = None
            if i in cap_hits_text:
                self.say(cap_hits_text[i], *plays, run_time=0.7, hold=0.5)
            else:
                self.play(*plays, run_time=0.6)
                self.wait(0.15)
            self.play(FadeOut(raw_boxes), run_time=0.2)
            if i == 5:
                self.say("It draws the **median** of the last 5 boxes", hold=0.5)
            if i == 6:
                self.say("Cap removed? The box leaves after a short delay", hold=0.2)
        self.wait(1.2)


SCENES = {
    "hsv": (HsvScene, "02a-hsv.gif"),
    "steady": (SteadyScene, "04-steady.gif"),
    "lock": (LockScene, "04b-lock.gif"),
    "cleanup": (CleanupScene, "07b-cleanup.gif"),
    "tracker": (TrackerScene, "07d-steady-boxes.gif"),
}


def render(key, width=800, fps=12):
    scene, filename = SCENES[key]
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene.__name__], check=True)
    mp4 = next(media.glob(f"videos/**/{scene.__name__}.mp4"))
    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / filename
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(f"{gif}  {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for name in sys.argv[1:] or SCENES:
        render(name)
