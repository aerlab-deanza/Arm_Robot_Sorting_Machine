"""Scenes 6-9: research, pipeline overview, segmentation, skeleton and path."""
import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, WHITE, Arrow, Circle, Create, Dot, FadeIn, FadeOut, FadeTransform,
    Indicate, Line, LaggedStart, Rectangle, SurroundingRectangle, VGroup, Write,
    ReplacementTransform, Transform, DashedLine, Brace, smooth, linear, Group,
)

from look import (BLUE, GREEN, GREY, RED, TEAL, YELLOW, Explainer, T, line_through, load_info,
                  picture, px_to_scene)


class S06Research(Explainer):
    """What researchers do: models and camera methods with published results."""

    def construct(self):
        self.title_card("What do researchers do?", "Only methods with published results")
        self.say("Numbers below are read from paper abstracts. Check the papers before quoting.",
                 size=26, where=DOWN * 3.4, hold=3)

        def block(rows, heading):
            head = T((heading, YELLOW), size=40).to_edge(UP, buff=0.6)
            group = VGroup()
            for source, claim in rows:
                group.add(VGroup(T(source, size=30, color=BLUE), T(claim, size=28)).arrange(DOWN, aligned_edge=LEFT, buff=0.12))
            group.arrange(DOWN, aligned_edge=LEFT, buff=0.55).next_to(head, DOWN, buff=0.6).align_to(head, LEFT)
            self.play(Write(head), run_time=1)
            for row in group:
                self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=1.0)
                self.wait(3.2)
            self.wait(1.5)
            self.play(FadeOut(group), FadeOut(head))

        block([
            ("Webster and Jones, 2010", "Constant curvature models: several styles give identical results."),
            ("Rucker and Webster, 2011", "Cosserat rod for tendon arms: any string path, any load."),
            ("Till, Aloi and Rucker, 2019", "Real-time Cosserat solver: about 9.5 kHz on a three-section robot."),
        ], "Models")
        block([
            ("Vision with arcs (early work, and Pedari et al.)", "A camera plus constant-curvature arcs gives the shape of a tendon arm."),
            ("arXiv 2405.15336", "Marker-free: fit a curve straight to the binary mask of the robot."),
            ("MoSS, RA-L 2024", "Learned, one RGB camera: 0.91 mm mean error, 70 fps, two-segment tendon robot."),
        ], "Cameras")
        mine = VGroup(T(("Our choice", YELLOW), size=44),
                      T("mask  ", r"$\to$", r"  centerline  ", r"$\to$", r"  fit an arc and a flexible curve", size=36),
                      T("A learned network only if this fails on real video.", size=30, color=GREY)).arrange(DOWN, buff=0.5)
        self.play(FadeIn(mine, shift=UP * 0.2))
        self.wait(5)


class S06bWhichModel(Explainer):
    """Sensing needs a curve family. Predicting needs physics."""

    def construct(self):
        self.title_card("PCC or Cosserat? It depends on the job")
        left = VGroup(T(("Sensing", BLUE), size=44), T("camera  ", r"$\to$", "  shape", size=34),
                      T("we already see the shape,", size=28, color=GREY), T("so we only need a curve family", size=28, color=GREY),
                      T(("arcs, flexible curvature", GREEN), size=30)).arrange(DOWN, buff=0.3).move_to(LEFT * 3.4 + UP * 0.6)
        right = VGroup(T(("Predicting", RED), size=44), T("string pull, weight  ", r"$\to$", "  shape", size=34),
                       T("nothing is seen,", size=28, color=GREY), T("so the physics must be in the model", size=28, color=GREY),
                       T(("Cosserat rod", YELLOW), size=30)).arrange(DOWN, buff=0.3).move_to(RIGHT * 3.4 + UP * 0.6)
        self.play(FadeIn(left, shift=RIGHT * 0.3), run_time=1.5)
        self.wait(5)
        self.play(FadeIn(right, shift=LEFT * 0.3), run_time=1.5)
        self.wait(5)
        self.say("Cosserat rods are more exact, and heavier to compute.", where=DOWN * 2.6, hold=3.5)
        self.say("One report: end-effector error 5.8 percent (Cosserat) against 8.3 percent (beam model), on a three-segment tendon robot.",
                 size=26, where=DOWN * 2.6, hold=5)
        self.say("Our job is sensing. A constant arc is the simplest model that can work, and the flexible curve covers gravity.",
                 size=28, where=DOWN * 2.6, hold=5)
        self.say("The Cosserat code is ready for later: predicting the shape from the string.", size=28, where=DOWN * 2.6, hold=4)


class S07Overview(Explainer):
    """The pipeline in one picture."""

    def construct(self):
        self.title_card("The whole pipeline, in one line")
        names = ["bent_frame", "bent_mask", "bent_skeleton", "bent_overlay"]
        images = [picture(n, 1.9) for n in names]
        row = Group(*images).arrange(RIGHT, buff=1.1).shift(UP * 0.5)
        arrows = [Arrow(images[i].get_right(), images[i + 1].get_left(), buff=0.12, color=GREY, stroke_width=3) for i in range(3)]
        labels = [T("camera picture", size=26, color=GREY), T(("mask", TEAL), size=28), T("skeleton", size=28, color=BLUE),
                  T(("fit", GREEN), size=28)]
        funcs = [T("", size=22), T(r"\texttt{segment\_arm}", size=24, color=GREY), T(r"\texttt{trace\_centerline}", size=24, color=GREY),
                 T(r"\texttt{fit\_pcc}", size=24, color=GREY)]
        for img, lab, fn in zip(images, labels, funcs):
            lab.next_to(img, DOWN, buff=0.2)
            fn.next_to(lab, DOWN, buff=0.12)
        frames = [Rectangle(width=i.width, height=i.height, color=GREY, stroke_width=1.5).move_to(i) for i in images]
        self.play(FadeIn(images[0]), FadeIn(frames[0]))
        self.play(FadeIn(labels[0]))
        for i in range(3):
            self.play(Create(arrows[i]), FadeIn(images[i + 1]), FadeIn(frames[i + 1]), FadeIn(labels[i + 1]), FadeIn(funcs[i + 1]), run_time=1.6)
            self.wait(1.5)
        nums = T(("tip $(x,y)$", RED), r",\quad ", (r"curvature $\kappa$", GREEN), r",\quad ", ("length $L$", BLUE), size=36).move_to(DOWN * 2.6)
        nums.move_to(np.array([images[3].get_x() - 2.2, -2.6, 0]))
        arrow_down = Arrow(funcs[3].get_bottom(), np.array([funcs[3].get_x(), nums.get_top()[1], 0]), buff=0.1, color=GREY, stroke_width=3)
        self.play(Create(arrow_down), FadeIn(nums))
        self.wait(2)
        smooth_note = T(r"then steady the numbers over frames: \texttt{ShapeSmoother}", size=28, color=GREY).next_to(nums, DOWN, buff=0.3)
        self.play(FadeIn(smooth_note))
        self.wait(2.5)
        self.say("Next: each step, with the real numbers from your recording.", where=UP * 3.4)


class S08bBiggestBlob(Explainer):
    """Why not simply take the biggest dark blob?"""

    def construct(self):
        import cv2
        from look import ASSETS
        self.title_card("First idea: take the biggest dark blob", "Why it fails")
        pos = LEFT * 2.8
        self.add(Rectangle(width=4.8 * 4 / 3, height=4.8, color=GREY, stroke_width=1.5).move_to(pos))
        frame = picture("bent_frame", 4.8).move_to(pos)
        dark = picture("bent_dark", 4.8).move_to(pos)
        self.play(FadeIn(frame))
        self.wait(1.5)
        self.play(FadeTransform(frame, dark), run_time=1.5)
        mask = cv2.imread(str(ASSETS / "bent_dark.png"), 0)
        count, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8))
        order = sorted(range(1, count), key=lambda i: -stats[i, cv2.CC_STAT_AREA])[:2]
        names = [("biggest blob", RED), ("second blob", GREY)]
        total = mask.shape[0] * mask.shape[1]
        rows = VGroup()
        for (name, color), idx in zip(names, order):
            x, y, w, h, area = stats[idx]
            a, b = px_to_scene(dark, x, y), px_to_scene(dark, x + w, y + h)
            rect = Rectangle(width=abs(b[0] - a[0]), height=abs(b[1] - a[1]), color=color, stroke_width=3).move_to((a + b) / 2)
            self.play(Create(rect), run_time=1)
            rows.add(T((name, color), rf"$\;$ {area / total * 100:.0f} percent of the picture", size=30))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.4).move_to(RIGHT * 3.6 + UP * 0.8)
        self.play(FadeIn(rows))
        self.wait(3)
        self.say("The biggest dark blob is the sleeve. The arm is only small dashes: the clips cut it.", where=DOWN * 3.4, hold=4)
        self.say("With a different sleeve or light it could be the laptop, or the arm. Clothes decide, not us.", where=DOWN * 3.4, hold=4)
        self.say("So we ask a better question: ", ("which dark shape is thin, and starts at the base?", YELLOW), where=DOWN * 3.4, hold=4)


class S08Segmentation(Explainer):
    """Mask: which pixels are the arm?"""

    def construct(self):
        info = load_info("bent")
        self.title_card("Step 1: which pixels are the arm?")
        stage = [("frame", "camera picture"), ("grey", "turn colors into brightness"), ("dark", "keep the dark pixels"),
                 ("dark_neutral", "drop reddish dark pixels"), ("thick", "find the thick dark shapes"),
                 ("thin", "cut the thick ones away"), ("closed", "close the gaps left by the clips"),
                 ("mask", "keep pieces that are big enough")]
        pos = LEFT * 2.8
        current = picture("bent_frame", 4.8).move_to(pos)
        self.add(Rectangle(width=4.8 * 4 / 3, height=4.8, color=GREY, stroke_width=1.5).move_to(pos))
        self.play(FadeIn(current))
        tag = T(("1", YELLOW), "  camera picture", size=30).to_corner(np.array([-1.0, 1.0, 0]), buff=0.5)
        self.play(FadeIn(tag))
        self.wait(2)

        def go(index, side_text=None, hold=3.0):
            nonlocal current, tag
            name, words = stage[index]
            new = picture(f"bent_{name}", 4.8).move_to(pos)
            new_tag = T((str(index + 1), YELLOW), "  " + words, size=30).to_corner(np.array([-1.0, 1.0, 0]), buff=0.5)
            self.play(FadeOut(current), FadeIn(new), ReplacementTransform(tag, new_tag), run_time=1.2)
            current, tag = new, new_tag
            if side_text is not None:
                self.play(FadeIn(side_text, shift=LEFT * 0.2))
            self.wait(hold)
            return side_text

        go(1)
        f1 = T(r"$g=0.299R+0.587G+0.114B$", size=34).move_to(RIGHT * 3.6 + UP * 1.5)
        self.play(Write(f1))
        self.wait(2.5)
        a = go(2)
        wall = T("wall brightness", r"$\;w$", " = 75th percentile", size=30).move_to(RIGHT * 3.6 + UP * 1.0)
        lim = T(r"limit $=\min\big(\text{Otsu},\ \max(25,\ 0.40\,w)\big)$", size=32).move_to(RIGHT * 3.6 + UP * 0.1)
        nums = T(rf"$\min(\,{info['otsu']:.0f},\ {0.40 * info['wall75']:.1f}\,)={info['limit']:.0f}$", size=34, color=YELLOW).move_to(RIGHT * 3.6 + DOWN * 0.9)
        self.play(FadeOut(f1), FadeIn(wall))
        self.play(Write(lim))
        self.play(Write(nums))
        self.wait(2.5)
        self.say("Pixels darker than the limit are kept. Sleeve, hand shadow, laptop and arm all pass.", where=DOWN * 3.4, hold=4)
        self.play(FadeOut(wall), FadeOut(lim), FadeOut(nums))
        self.next_section("thick")
        go(3)
        rule = T(r"keep a dark pixel if", r"\quad $B>0.25\,(R+3)$", size=32).move_to(RIGHT * 3.6 + UP * 0.8)
        why = T("skin in shadow is reddish: blue is weak.", size=28, color=GREY).move_to(RIGHT * 3.6 + DOWN * 0.1)
        why2 = T("the black arm is neutral.", size=28, color=GREY).next_to(why, DOWN, buff=0.2)
        self.play(Write(rule))
        self.play(FadeIn(why), FadeIn(why2))
        self.wait(4)
        self.play(FadeOut(rule), FadeOut(why), FadeOut(why2))
        go(4)
        ex = T(r"\textbf{opening}: erode, then grow back", size=32).move_to(RIGHT * 3.6 + UP * 1.0)
        ex2 = T(r"disc wider than the arm:", size=28, color=GREY).move_to(RIGHT * 3.6 + UP * 0.1)
        ex3 = T("thin things vanish, only the sleeve stays.", size=28, color=GREY).next_to(ex2, DOWN, buff=0.2)
        self.play(Write(ex), FadeIn(ex2), FadeIn(ex3))
        self.wait(5)
        self.play(FadeOut(ex), FadeOut(ex2), FadeOut(ex3))
        self.next_section("gaps")
        go(5)
        t1 = T(r"thin $=$ dark $-$ (thick, slightly grown)", size=32).move_to(RIGHT * 3.6 + UP * 0.8)
        t2 = T("The arm is left in pieces: the clips cut it.", size=28, color=GREY).move_to(RIGHT * 3.6 + DOWN * 0.2)
        self.play(Write(t1), FadeIn(t2))
        self.wait(4.5)
        self.play(FadeOut(t1), FadeOut(t2))
        go(6)
        c1 = T(r"\textbf{closing}: grow, then shrink", size=32).move_to(RIGHT * 3.6 + UP * 0.9)
        c2 = T(rf"disc of {info['kernel']} px bridges the clip gaps.", size=28, color=GREY).move_to(RIGHT * 3.6 + DOWN * 0.1)
        self.play(Write(c1), FadeIn(c2))
        self.wait(4.5)
        self.play(FadeOut(c1), FadeOut(c2))
        go(7)
        m1 = T("Many shapes remain: the arm, and the laptop edge.", size=28, color=GREY).move_to(RIGHT * 3.6 + UP * 0.4)
        m2 = T(("We do not choose yet.", YELLOW), " The base will choose.", size=28).next_to(m1, DOWN, buff=0.25)
        self.play(FadeIn(m1), FadeIn(m2))
        self.wait(5)


class S09Skeleton(Explainer):
    """Skeleton and path from the base."""

    def construct(self):
        info = load_info("bent")
        self.title_card("Step 2: the middle line of the arm")
        self.add(Rectangle(width=4.8 * 4 / 3, height=4.8, color=GREY, stroke_width=1.5).move_to(LEFT * 2.8))
        mask = picture("bent_mask", 4.8).move_to(LEFT * 2.8)
        skeleton = picture("bent_skeleton", 4.8).move_to(LEFT * 2.8)
        self.play(FadeIn(mask))
        self.wait(1.5)
        self.play(FadeTransform(mask, skeleton), run_time=2)
        self.say(("Skeleton", BLUE), ": thin every shape down to a one-pixel line.", where=DOWN * 3.4)
        frame = picture("bent_frame", 4.8).move_to(LEFT * 2.8)

        base = px_to_scene(skeleton, *info["base"])
        base_dot = Dot(base, color=YELLOW, radius=0.1)
        base_label = T(("base", YELLOW), size=28).next_to(base_dot, DOWN, buff=0.15)
        self.play(FadeIn(base_dot, scale=2), FadeIn(base_label))
        self.say("The ", ("base", YELLOW), " is the point you click. The arm is the line that starts there.", where=DOWN * 3.4, hold=3.5)

        path = np.array(info["skeleton_path"])
        scene_path = np.array([px_to_scene(skeleton, x, y) for x, y in path[::3]])
        dots = VGroup(*[Dot(p, radius=0.03, color=BLUE) for p in scene_path])
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.02), run_time=3.5)
        tip_dot = Dot(px_to_scene(skeleton, *path[-1]), color=RED, radius=0.09)
        self.play(FadeIn(tip_dot, scale=2))
        self.say("Walk from the base along the line. The ", ("farthest point", RED), " is the tip.", where=DOWN * 3.4)

        laptop = SurroundingRectangle(Rectangle(width=0.9, height=0.9).move_to(px_to_scene(skeleton, 600, 400)), color=RED, buff=0.0)
        self.play(Create(laptop))
        self.say("Other dark shapes, like the laptop, are not connected to the base: ", ("ignored", RED), ".", where=DOWN * 3.4, hold=3.5)
        self.play(FadeOut(laptop))

        self.next_section("shadows")
        # right side: why a shadow branch cannot win, as a diagram
        main = [np.array([1.0 + 0.45 * i, -1.2 + 0.3 * np.sin(i * 0.5), 0]) for i in range(8)]
        branch = [main[3] + np.array([0.3 * j, -0.4 * j, 0]) for j in range(1, 3)]
        diagram = VGroup(*[Dot(p, radius=0.06, color=BLUE) for p in main], *[Dot(p, radius=0.06, color=RED) for p in branch])
        links = VGroup(*[Line(main[i], main[i + 1], color=BLUE, stroke_width=3) for i in range(7)],
                       Line(main[3], branch[0], color=RED, stroke_width=3), Line(branch[0], branch[1], color=RED, stroke_width=3))
        diagram.shift(UP * 2.3 + LEFT * 0.0)
        links.shift(UP * 2.3)
        self.play(FadeIn(links), FadeIn(diagram))
        d_main = T(("long path: the arm", BLUE), size=26).next_to(links, UP, buff=0.35)
        d_branch = T(("short branch: a shadow", RED), size=26).next_to(links, DOWN, buff=0.75)
        self.play(FadeIn(d_main), FadeIn(d_branch))
        self.say("A short side branch, like a shadow under the hand, is shorter than the arm. The farthest point wins.", where=DOWN * 3.4, hold=4.5)
        self.play(FadeOut(links), FadeOut(diagram), FadeOut(d_main), FadeOut(d_branch))

        # ends are pushed out by one half-width
        cap_y = 1.7
        arm_body = Rectangle(width=3.2, height=0.8, color=BLUE, fill_opacity=0.35).move_to(RIGHT * 3.5 + UP * cap_y)
        mid = Line(arm_body.get_left() + RIGHT * 0.4, arm_body.get_right() + LEFT * 0.4, color=WHITE, stroke_width=3)
        self.play(FadeIn(arm_body), Create(mid))
        r_arrow = Arrow(mid.get_end(), arm_body.get_right(), buff=0, color=RED, stroke_width=4, max_tip_length_to_length_ratio=0.3)
        r_label = T(("half width", RED), size=26).next_to(arm_body, DOWN, buff=0.2)
        self.play(Create(r_arrow), FadeIn(r_label))
        self.say("A skeleton stops one ", ("half width", RED), " before the real end. We push both ends out by that much.", where=DOWN * 3.4, hold=4)
        self.play(FadeOut(arm_body), FadeOut(mid), FadeOut(r_arrow), FadeOut(r_label))

        smooth = T("then: even steps of 4 px,", size=30).move_to(RIGHT * 3.6 + UP * 1.2)
        smooth2 = T("average each point with its 4 neighbours.", size=30).next_to(smooth, DOWN, buff=0.2)
        self.play(FadeIn(smooth), FadeIn(smooth2))
        self.wait(4)
        for m in (skeleton, base_dot, base_label, dots, tip_dot):
            self.remove(m)
        self.add(frame)
        poly = line_through([px_to_scene(frame, x, y) for x, y in zip(*np.array(info["skeleton_path"]).T[::1])][::4], BLUE, 5)
        self.play(Create(poly), run_time=2)
        self.say("Result: the ", ("backbone", BLUE), " as an ordered list of points, base to tip.", where=DOWN * 3.4, hold=3.5)
