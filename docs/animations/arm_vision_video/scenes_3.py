"""Scenes 10-14: fit, coordinates, smoothing, results and limits, recap."""
import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Axes, Create, Dot, FadeIn, FadeOut, Group, Line, Rectangle,
    VGroup, Write, LaggedStart, Transform, ReplacementTransform, Indicate,
)

from look import (BLUE, GREEN, GREY, RED, TEAL, YELLOW, Explainer, T, line_through, load_info,
                  load_stats, picture, px_to_scene)


class S10Fit(Explainer):
    """Fit an arc, then a flexible curve, to the backbone points."""

    def error_bowl(self, info, pts, axes, formula, goal, goal2):
        """Slide the curvature and watch the error: the best value is the bottom of the bowl."""
        import shape_models
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        length, theta0 = info["pcc"]["length"], info["pcc"]["base_angle"]
        grid = np.linspace(0, length, 400)

        def model(kappa):
            return shape_models.pcc_points(kappa, length, 400, theta0, tuple(pts[0]))

        def rms(kappa):
            m = model(kappa)
            dx = np.interp(s * length / s[-1], grid, m[:, 0]) - pts[:, 0]
            dy = np.interp(s * length / s[-1], grid, m[:, 1]) - pts[:, 1]
            return float(np.sqrt(np.mean(dx ** 2 + dy ** 2)))

        ks = np.linspace(0.0, 0.02, 60)
        errs = np.array([rms(k) for k in ks])
        top = float(np.ceil(min(errs.max(), 80) / 20) * 20)
        bowl = Axes(x_range=[0, 0.02, 0.005], y_range=[0, top, 20], x_length=4.0, y_length=2.4,
                    axis_config={"color": GREY, "include_tip": False, "font_size": 18}).move_to(RIGHT * 3.9 + DOWN * 1.3)
        bl = T(r"$\kappa$", size=24, color=GREY).next_to(bowl, DOWN, buff=0.1)
        yl = T(("error (px)", RED), size=24).next_to(bowl, UP, buff=0.1)
        curve = bowl.plot_line_graph(ks, np.clip(errs, 0, top), line_color=RED, add_vertex_dots=False, stroke_width=4)
        self.play(FadeIn(bowl), FadeIn(bl), FadeIn(yl), Create(curve), run_time=2)

        def at(k):
            dot = Dot(bowl.c2p(ks[k], min(errs[k], top)), color=YELLOW, radius=0.09)
            line = line_through([axes.c2p(x, y) for x, y in model(ks[k])[::8]], YELLOW, 4)
            return dot, line

        tracker, guess = at(5)
        self.play(FadeIn(tracker), Create(guess))
        self.wait(1.5)
        for k in (12, 25, 40, 50, int(np.argmin(errs))):
            new_dot, new_line = at(k)
            self.play(Transform(tracker, new_dot), Transform(guess, new_line), run_time=1.6)
            self.wait(1.0)
        self.say("Try every curvature. The best one is the ", ("bottom of the bowl", YELLOW), ".", where=DOWN * 3.4, hold=3.5)
        self.play(FadeOut(guess), FadeOut(tracker), FadeOut(bowl), FadeOut(bl), FadeOut(yl), FadeOut(curve))

    def construct(self):
        info = load_info("bent")
        self.title_card("Step 3: fit a curve to the points")
        pts = np.array(info["backbone"])
        pcc_fit = np.array(info["pcc"]["fit"])
        poly_fit = np.array(info["poly"]["fit"])
        axes = Axes(x_range=[-200, 20, 50], y_range=[-20, 180, 50], x_length=7.2, y_length=5.2,
                    axis_config={"color": GREY, "include_tip": False, "font_size": 20}).shift(LEFT * 3.4 + DOWN * 0.2)
        ax_label = T("pixels from the base, y up", size=24, color=GREY).next_to(axes, DOWN, buff=0.2)
        self.play(FadeIn(axes), FadeIn(ax_label))
        dots = VGroup(*[Dot(axes.c2p(x, y), radius=0.035, color=BLUE) for x, y in pts[::2]])
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.02), run_time=3)
        self.say("The points from step 2, relative to the ", ("base", YELLOW), ".", where=DOWN * 3.4)

        formula = T(r"$\theta(s)=\theta_0+\kappa s$", size=38).move_to(RIGHT * 3.6 + UP * 2.4)
        goal = T(r"find $\kappa,\ \theta_0$ that", size=30).next_to(formula, DOWN, buff=0.35)
        goal2 = T(r"minimise  $\sum_i \lVert p_i - m_i\rVert^2$", size=32).next_to(goal, DOWN, buff=0.2)
        self.play(Write(formula))
        self.play(FadeIn(goal), FadeIn(goal2))
        self.wait(3)
        self.error_bowl(info, pts, axes, formula, goal, goal2)
        self.next_section("flexible")
        arc = line_through([axes.c2p(x, y) for x, y in pcc_fit[::4]], GREEN, 5)
        self.play(Create(arc), run_time=2)
        # error bars: from each point to the arc
        residuals = VGroup()
        for x, y in pts[::10]:
            k = int(np.argmin(np.hypot(pcc_fit[:, 0] - x, pcc_fit[:, 1] - y)))
            residuals.add(Line(axes.c2p(x, y), axes.c2p(*pcc_fit[k]), color=RED, stroke_width=3))
        self.play(Create(residuals))
        rms = T(("error", RED), rf"$\;$ {info['pcc']['rms_px']:.1f} px  (one arc)", size=32).move_to(RIGHT * 3.6 + DOWN * 0.6)
        self.play(FadeIn(rms))
        self.say("One arc: close, but the arm is straight near the hand, bent in the middle.", where=DOWN * 3.4, hold=4)
        self.play(FadeOut(arc), FadeOut(residuals))

        c0, c1, c2 = info["poly"]["coeffs"]
        flex = T(r"$\kappa(u)=c_0+c_1u+c_2u^2$", size=34).move_to(formula)
        self.play(ReplacementTransform(formula, flex))
        u_note = T(r"$u$: 0 at the base, 1 at the tip", size=26, color=GREY).next_to(flex, DOWN, buff=0.2)
        self.play(FadeOut(goal), FadeOut(goal2), FadeIn(u_note))
        curve = line_through([axes.c2p(x, y) for x, y in poly_fit[::4]], GREEN, 5)
        self.play(Create(curve), run_time=2)
        new_rms = T(("error", RED), rf"$\;$ {info['poly']['rms_px']:.1f} px  (flexible)", size=32).move_to(rms)
        self.play(Transform(rms, new_rms))
        nums = T(rf"$c_0={c0:.3f},\ c_1={c1:.3f},\ c_2={c2:.3f}$", size=28, color=GREY).move_to(RIGHT * 3.6 + DOWN * 1.5)
        self.play(FadeIn(nums))
        self.say("Curvature may change along the arm. One arc is the special case ", r"$c_1=c_2=0$", ".", where=DOWN * 3.4, hold=4)
        gate = T(("Small error", GREEN), " = one clean curve.", size=28).move_to(RIGHT * 3.6 + DOWN * 2.4)
        gate2 = T(("Big error", RED), " = something else joined the mask.", size=28).next_to(gate, DOWN, buff=0.2)
        self.play(FadeIn(gate), FadeIn(gate2))
        self.wait(5)
        self.say("The tip is the last point. ", ("Length", BLUE), " is the length of the curve.", where=DOWN * 3.4)


class S11Coordinates(Explainer):
    """From pixels to x, y."""

    def construct(self):
        info = load_info("bent")
        self.title_card("Where do x and y come from?")
        image = picture("bent_frame", 5.4).move_to(LEFT * 3.2)
        self.add(Rectangle(width=5.4 * 4 / 3, height=5.4, color=GREY, stroke_width=1.5).move_to(LEFT * 3.2))
        self.play(FadeIn(image))
        bx, by = info["base"]
        tx, ty = bx + info["tip"][0], by - info["tip"][1]
        base_dot = Dot(px_to_scene(image, bx, by), color=YELLOW, radius=0.1)
        tip_dot = Dot(px_to_scene(image, tx, ty), color=RED, radius=0.1)
        self.play(FadeIn(base_dot, scale=2), FadeIn(T(("base", YELLOW), size=26).next_to(base_dot, DOWN, buff=0.1)))
        self.play(FadeIn(tip_dot, scale=2), FadeIn(T(("tip", RED), size=26).next_to(tip_dot, UP, buff=0.1)))
        self.wait(1.5)
        axis_x = Arrow(base_dot.get_center(), base_dot.get_center() + RIGHT * 1.4, buff=0, color=GREY, stroke_width=3)
        axis_y = Arrow(base_dot.get_center(), base_dot.get_center() + UP * 1.4, buff=0, color=GREY, stroke_width=3)
        lx, ly = T("x", size=26, color=GREY).next_to(axis_x, RIGHT, buff=0.05), T("y", size=26, color=GREY).next_to(axis_y, UP, buff=0.05)
        self.play(Create(axis_x), Create(axis_y), FadeIn(lx), FadeIn(ly))
        self.say("Origin at the base. ", ("x", GREY), " to the right, ", ("y", GREY), " up.", where=DOWN * 3.4)
        rows = VGroup(
            T(rf"base pixel $=({bx:.0f},\ {by:.0f})$", size=32, color=YELLOW),
            T(rf"tip pixel $=({tx:.1f},\ {ty:.1f})$", size=32, color=RED),
            T(rf"$x = {tx:.1f}-{bx:.0f} = {tx - bx:.1f}$", size=34),
            T(rf"$y = {by:.0f}-{ty:.1f} = {by - ty:.1f}$", size=34),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4).move_to(RIGHT * 3.4 + UP * 0.8)
        for row in rows:
            self.play(FadeIn(row, shift=LEFT * 0.2), run_time=1)
            self.wait(1.6)
        self.say("Picture rows grow downward, so ", ("y", GREY), " flips sign.", where=DOWN * 3.4)
        note = T(("pixels, not millimetres", YELLOW), size=32).move_to(RIGHT * 3.4 + DOWN * 1.4)
        self.play(FadeIn(note))
        self.wait(2)
        mm = VGroup(
            T(r"put a ruler on the wall, in the arm's plane", size=26, color=GREY),
            T(r"$\text{px/mm}=\dfrac{\text{ruler length in px}}{\text{ruler length in mm}}$", size=30),
            T(r"$x_{mm}=x/\text{px/mm}$", size=30),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.3).move_to(RIGHT * 3.4 + DOWN * 2.2)
        self.play(FadeOut(note), FadeIn(mm))
        self.wait(6)
        self.play(FadeOut(mm), FadeOut(rows))
        ex = VGroup(
            T(("Example, not measured:", YELLOW), size=28),
            T(r"suppose the arm is 200 mm long", size=28),
            T(r"the program measures 293 px along it", size=28),
            T(r"$\text{px/mm}=293/200=1.47$", size=32),
            T(rf"$x={tx - bx:.1f}\ \text{{px}}\;\to\;{(tx - bx) / 1.47:.0f}\ \text{{mm}}$", size=32),
            T(rf"$y={by - ty:.1f}\ \text{{px}}\;\to\;{(by - ty) / 1.47:.0f}\ \text{{mm}}$", size=32),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.28).move_to(RIGHT * 3.4 + UP * 0.3)
        self.play(FadeIn(ex))
        self.wait(8)


class S12Smoothing(Explainer):
    """Steady the numbers over time."""

    def construct(self):
        stats = load_stats()
        self.title_card("Step 4: steady the numbers")
        frames = [r["frame"] for r in stats if "raw_tip" in r]
        raw = [r["raw_tip"][0] for r in stats if "raw_tip" in r]
        steady_frames = [r["frame"] for r in stats if "tip" in r]
        steady = [r["tip"][0] for r in stats if "tip" in r]
        axes = Axes(x_range=[0, 450, 100], y_range=[-200, 20, 50], x_length=7.0, y_length=4.2,
                    axis_config={"color": GREY, "include_tip": False, "font_size": 20}).shift(LEFT * 3.0 + DOWN * 0.2)
        xl = T("frame", size=24, color=GREY).next_to(axes, DOWN, buff=0.15)
        yl = T("tip x (pixels)", size=24, color=GREY).next_to(axes, UP, buff=0.15)
        self.play(FadeIn(axes), FadeIn(xl), FadeIn(yl))
        raw_line = axes.plot_line_graph(frames, raw, line_color=RED, add_vertex_dots=False, stroke_width=2)
        self.play(Create(raw_line), run_time=4)
        self.say("Each frame gives a slightly different tip. One bad frame can jump.", where=DOWN * 3.4, hold=3.5)
        steady_line = axes.plot_line_graph(steady_frames, steady, line_color=GREEN, add_vertex_dots=False, stroke_width=4)
        rule = T(r"$s_t=(1-\alpha)\,s_{t-1}+\alpha\,x_t,\qquad \alpha=0.4$", size=32).move_to(RIGHT * 3.9 + UP * 1.6)
        self.play(Write(rule))
        self.play(Create(steady_line), run_time=4)
        self.say(("Red", RED), ": every frame.  ", ("Green", GREEN), ": blended with the past.", where=DOWN * 3.4)
        gates = VGroup(
            T(("A frame is skipped when", YELLOW), size=28),
            T(r"the flexible fit error $>3\%$ of length,", size=26),
            T(r"or the length jumps $>25\%$.", size=26),
            T(r"The last good values are held,", size=26, color=GREY),
            T(r"for at most 10 frames.", size=26, color=GREY),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.22).move_to(RIGHT * 3.9 + DOWN * 0.7)
        for g in gates:
            self.play(FadeIn(g, shift=LEFT * 0.15), run_time=0.8)
            self.wait(1.2)
        self.wait(3)
        step = lambda xs, ys: np.linalg.norm(np.diff(np.array([xs, ys]).T, axis=0), axis=1)  # noqa: E731
        raw_xy = np.array([r["raw_tip"] for r in stats if "raw_tip" in r])
        steady_xy = np.array([r["tip"] for r in stats if "tip" in r])
        raw_step = np.linalg.norm(np.diff(raw_xy, axis=0), axis=1)
        steady_step = np.linalg.norm(np.diff(steady_xy, axis=0), axis=1)
        result = T(rf"worst jump between frames: ", (rf"{raw_step.max():.0f} px", RED), r"  $\to$  ", (rf"{steady_step.max():.0f} px", GREEN), size=30).move_to(DOWN * 3.4)
        self.play(FadeIn(result))
        self.wait(5)


class S13Results(Explainer):
    """What the numbers say, what is not proven, how to check."""

    def construct(self):
        stats = load_stats()
        n = len(stats)
        found = sum(r["found"] for r in stats)
        used = sum(r["used"] for r in stats)
        steady_xy = np.array([r["tip"] for r in stats if "tip" in r])
        step = np.linalg.norm(np.diff(steady_xy, axis=0), axis=1)
        self.title_card("What did we measure?", "One real recording: arm straight and bent, a sleeve, a hand, a laptop")
        rows = [
            (f"{found} of {n}", "frames: the arm was found"),
            (f"{used} of {found}", "found frames passed the quality checks"),
            (f"{np.percentile(step, 50):.1f} px", "typical tip movement between frames"),
            (f"{np.percentile(step, 99):.0f} px", "99 percent of frames move less than this"),
            ("about 20 fps", "on a normal PC, 640 by 480"),
        ]
        group = VGroup(*[VGroup(T((a, YELLOW), size=40), T(b, size=30, color=GREY)).arrange(RIGHT, buff=0.5) for a, b in rows])
        group.arrange(DOWN, aligned_edge=LEFT, buff=0.45).move_to(UP * 0.4)
        for row in group:
            self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=1)
            self.wait(2)
        self.wait(2)
        self.play(FadeOut(group))

        self.next_section("not_proven")
        head = T(("Not yet proven", RED), size=44).to_edge(UP, buff=0.7)
        self.play(Write(head))
        limits = VGroup(
            T(("Millimetres:", YELLOW), " no ruler scale set yet, so everything is in pixels.", size=30),
            T(("Camera angle:", YELLOW), " no lens or tilt correction. Face the wall squarely.", size=30),
            T(("Out of plane:", YELLOW), " bending toward the camera shrinks the 2D curve.", size=30),
            T(("Tip:", YELLOW), " the end of the last dark piece, not the end of the last clip.", size=30),
            T(("Hands:", YELLOW), " fingers covering the arm hide it.", size=30),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4).next_to(head, DOWN, buff=0.7)
        for line in limits:
            self.play(FadeIn(line, shift=RIGHT * 0.2), run_time=0.9)
            self.wait(2.4)
        self.wait(2)
        self.play(FadeOut(limits), FadeOut(head))
        self.next_section("check")
        how = T(("How to check by hand", GREEN), size=44).to_edge(UP, buff=0.7)
        steps = VGroup(
            T(r"1. Tape a ruler on the wall, in the arm's plane.", size=30),
            T(r"2. Take a picture. Measure two ruler marks in pixels: set px/mm.", size=30),
            T(r"3. Hold the arm still. Measure the true tip with the ruler.", size=30),
            T(r"4. Compare with the program's tip. Repeat for 5 to 10 shapes.", size=30),
            T(r"5. Hold still for 5 s: the spread of the tip is the noise.", size=30),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4).next_to(how, DOWN, buff=0.7)
        self.play(Write(how))
        for s in steps:
            self.play(FadeIn(s, shift=RIGHT * 0.2), run_time=0.9)
            self.wait(2.6)
        self.wait(3)


class S14Recap(Explainer):
    """Recap and next steps."""

    def construct(self):
        self.title_card("Recap")
        names = ["bent_frame", "bent_mask", "bent_skeleton", "bent_overlay"]
        images = [picture(n, 1.7) for n in names]
        row = Group(*images).arrange(RIGHT, buff=0.7).shift(UP * 1.6)
        frames = [Rectangle(width=i.width, height=i.height, color=GREY, stroke_width=1.5).move_to(i) for i in images]
        words = ["picture", "mask", "centerline", "fit"]
        cols = [GREY, TEAL, BLUE, GREEN]
        labels = [T((w, c), size=26).next_to(i, DOWN, buff=0.15) for w, c, i in zip(words, cols, images)]
        for img, fr, lab in zip(images, frames, labels):
            self.play(FadeIn(img), FadeIn(fr), FadeIn(lab), run_time=0.9)
        points = VGroup(
            T(("mask", TEAL), ": dark, not reddish, thin, clip gaps closed", size=28),
            T(("centerline", BLUE), ": skeleton, path from the base, ends pushed out", size=28),
            T(("fit", GREEN), ": arc ", r"$\kappa$", " and flexible curve, tip, length", size=28),
            T(("steady", YELLOW), ": blend frames, skip bad ones", size=28),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.3).move_to(DOWN * 0.7)
        for p in points:
            self.play(FadeIn(p, shift=RIGHT * 0.2), run_time=0.8)
            self.wait(1.8)
        self.wait(2)
        self.play(FadeOut(points))
        nxt = T(("Next", YELLOW), size=44).move_to(DOWN * 0.1)
        items = VGroup(
            T("Set the scale: pixels to millimetres, and check the error with a ruler.", size=28),
            T(r"Link to the string: $\kappa=\Delta\ell/(dL)$ tells how far to pull.", size=28),
            T("Use the Cosserat model only if we need to predict the shape from forces.", size=28),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.35).next_to(nxt, DOWN, buff=0.5)
        self.play(Write(nxt))
        for it in items:
            self.play(FadeIn(it, shift=RIGHT * 0.2), run_time=0.9)
            self.wait(2.6)
        self.wait(4)
