"""Scenes 1-5: the question, the real picture, describing a curve, tendon, gravity."""
import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, WHITE, BLACK, Arrow, Axes, Circle, Create, Dot, DoubleArrow,
    FadeIn, FadeOut, Line, Polygon, Rectangle, Transform, ValueTracker, VGroup, Write,
    always_redraw, linear, smooth, Arc, MathTex, Indicate, SurroundingRectangle,
    FadeTransform, ReplacementTransform, LaggedStart, AnimationGroup,
)

from look import (BLUE, GREEN, GREY, RED, TEAL, WALL, YELLOW, Explainer, T, line_through,
                  load_info, pcc, picture, px_to_scene)
import shape_models


def offset_curve(points, distance):
    """Curve shifted to the left of the direction of travel by `distance`."""
    tangent = np.gradient(points[:, :2], axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True) + 1e-9
    normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)
    out = points.copy()
    out[:, :2] += distance * normal
    return out


def clips_on(points, count=6, size=0.32):
    """White clips across the arm, like on the real one."""
    group = VGroup()
    for i in np.linspace(0.12, 0.98, count):
        k = int(i * (len(points) - 1))
        tangent = points[min(k + 1, len(points) - 1), :2] - points[max(k - 1, 0), :2]
        tangent /= np.linalg.norm(tangent) + 1e-9
        normal = np.array([-tangent[1], tangent[0]])
        a = np.append(points[k, :2] + normal * size / 2, 0)
        b = np.append(points[k, :2] - normal * size / 2, 0)
        group.add(Line(a, b, color=WHITE, stroke_width=5))
    return group


class S01Question(Explainer):
    """A tendon arm bends. A camera watches. What do we want from the picture?"""

    def construct(self):
        self.title_card("A robot arm, pulled by a string", "From a camera picture: what shape is it?")
        wall = Rectangle(width=7.0, height=5.0, fill_color=WALL, fill_opacity=1, stroke_width=0).shift(RIGHT * 2.2)
        base = np.array([2.2, -2.0, 0.0])
        camera = VGroup(Rectangle(width=0.9, height=0.6, color=GREY, fill_color="#222222", fill_opacity=1),
                        Circle(radius=0.2, color=GREY)).shift(LEFT * 5.2)
        cone = Polygon(camera.get_right(), wall.get_corner(np.array([-1, 1, 0])), wall.get_corner(np.array([-1, -1, 0])),
                       stroke_width=0, fill_color=WHITE, fill_opacity=0.07)
        self.play(FadeIn(wall), FadeIn(camera), FadeIn(cone), run_time=1.5)

        kappa = ValueTracker(0.0)
        length = 3.4
        arm = always_redraw(lambda: line_through(pcc(kappa.get_value() + 1e-4, length, base), BLACK, 18))
        tendon = always_redraw(lambda: line_through(offset_curve(pcc(kappa.get_value() + 1e-4, length, base), 0.2), RED, 3))
        clips = always_redraw(lambda: clips_on(pcc(kappa.get_value() + 1e-4, length, base)))
        self.play(FadeIn(arm), FadeIn(tendon), FadeIn(clips))
        label = T(("tendon", RED), size=28).next_to(base + np.array([-0.3, 0.9, 0]), LEFT)
        self.play(FadeIn(label))
        self.wait(1)
        self.play(kappa.animate.set_value(0.5), run_time=4, rate_func=smooth)
        self.wait(1)
        self.play(kappa.animate.set_value(-0.35), run_time=3.5, rate_func=smooth)
        self.play(kappa.animate.set_value(0.3), run_time=2.5, rate_func=smooth)
        self.play(FadeOut(label))

        tip = always_redraw(lambda: Dot(pcc(kappa.get_value() + 1e-4, length, base)[-1], color=RED, radius=0.11))
        self.play(FadeIn(tip, scale=2))
        tip_label = always_redraw(lambda: T(("tip", RED), r"$\;(x,\,y)$", size=30).next_to(tip, UP, buff=0.2))
        self.play(FadeIn(tip_label))
        self.say("Goal 1: where is the ", ("tip", RED), r"$\;(x,\,y)$?")
        curve = always_redraw(lambda: line_through(pcc(kappa.get_value() + 1e-4, length, base), GREEN, 3))
        self.play(Create(curve))
        self.say("Goal 2: what is the ", ("curve", GREEN), " of the arm?")
        self.say("Only from the camera picture. No markers. At least 15 times a second.")
        self.play(kappa.animate.set_value(0.1), run_time=2)
        self.wait(1)


class S02RealPicture(Explainer):
    """The real picture is messy: sleeve, hand, laptop, clips."""

    def construct(self):
        self.title_card("The real picture is messy")
        img = picture("bent_frame", 6.0).shift(LEFT * 2.2)
        self.play(FadeIn(img), run_time=1.5)
        self.wait(1.5)

        def box(x0, y0, x1, y1, color=RED):
            a, b = px_to_scene(img, x0, y0), px_to_scene(img, x1, y1)
            rect = Rectangle(width=abs(b[0] - a[0]), height=abs(b[1] - a[1]), color=color, stroke_width=4)
            rect.move_to((a + b) / 2)
            return rect

        items = [("dark sleeve", box(0, 150, 270, 340), RED), ("hand", box(250, 235, 365, 325), RED),
                 ("dark laptop", box(520, 340, 640, 480), RED), ("the arm", box(150, 165, 385, 330), BLUE)]
        names = VGroup(*[T((name, color), size=34) for name, _, color in items]).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        names.move_to(RIGHT * 4.9)
        for (name, rect, color), text in zip(items, names):
            link = Line(rect.get_right(), text.get_left() + LEFT * 0.15, color=color, stroke_width=2)
            self.play(Create(rect), Create(link), FadeIn(text, shift=LEFT * 0.3), run_time=1.1)
            self.wait(0.8)
        self.wait(1)
        self.say("A dark sleeve is almost as dark as the arm.", where=DOWN * 3.3)
        self.say("White clips cut the arm into pieces.", where=DOWN * 3.3)
        self.say("The program must still find ", ("only the arm", BLUE), ".", where=DOWN * 3.3)


class S03Curve(Explainer):
    """A curve is described by how fast its direction turns."""

    def construct(self):
        self.title_card("How do you describe a curve with a few numbers?")
        base = np.array([-1.4, -2.4, 0.0])
        length = 3.8
        kappa = ValueTracker(0.45)
        s = ValueTracker(0.0)

        def pts():
            return pcc(kappa.get_value() + 1e-4, length, base)

        arc = always_redraw(lambda: line_through(pts(), BLUE, 7))
        self.play(Create(arc), run_time=1.5)
        dot = always_redraw(lambda: Dot(pcc(kappa.get_value() + 1e-4, length, base, n=200)[int(s.get_value() / length * 199)], color=YELLOW))

        def tangent_arrow():
            p = pcc(kappa.get_value() + 1e-4, length, base, n=200)
            k = int(s.get_value() / length * 199)
            theta = np.pi / 2 + kappa.get_value() * s.get_value()
            direction = np.array([np.cos(theta), np.sin(theta), 0])
            return Arrow(p[k], p[k] + 1.1 * direction, buff=0, color=YELLOW, stroke_width=5)

        arrow = always_redraw(tangent_arrow)
        self.play(FadeIn(dot), FadeIn(arrow))
        axes = Axes(x_range=[0, 3.8, 1], y_range=[0, 2.4, 1], x_length=4.2, y_length=3.0,
                    axis_config={"color": GREY, "include_tip": False, "font_size": 24}).shift(RIGHT * 3.0 + UP * 0.2)
        x_label = T("distance along the arm", r"$\;s$", size=26, color=GREY).next_to(axes, DOWN, buff=0.15)
        y_label = T("direction turned", r"$\;\theta$", size=26, color=GREY).next_to(axes, UP, buff=0.15)
        graph = always_redraw(lambda: axes.plot(lambda x: kappa.get_value() * x, x_range=[0, length], color=GREEN, stroke_width=5))
        mark = always_redraw(lambda: Dot(axes.c2p(s.get_value(), kappa.get_value() * s.get_value()), color=YELLOW, radius=0.08))
        self.play(FadeIn(axes), FadeIn(x_label), FadeIn(y_label))
        self.play(Create(graph), FadeIn(mark))
        self.play(s.animate.set_value(length), run_time=5, rate_func=linear)
        self.play(s.animate.set_value(0.0), run_time=1.2)
        self.say("As you walk along the arm, the direction ", "turns at a steady rate.")
        rule = T(r"$\theta(s)=\theta_0+$", (r"$\kappa$", YELLOW), r"$\,s$", size=44).move_to(UP * 3.0 + RIGHT * 3.0)
        self.play(Write(rule))
        meaning = T(("curvature", YELLOW), r"$\;\kappa$: how fast the direction turns", size=30, color=GREY).next_to(rule, DOWN)
        self.play(FadeIn(meaning))
        self.wait(1.5)
        self.play(kappa.animate.set_value(0.15), run_time=3)
        self.play(kappa.animate.set_value(0.6), run_time=3)
        self.play(kappa.animate.set_value(0.45), run_time=2)
        self.say("Constant ", ("curvature", YELLOW), " means the arm is a ", ("circular arc", BLUE), ".")
        self.say("Three numbers fix the whole arm: ", r"$\kappa,\ \theta_0,\ L$", ".")
        formulas = VGroup(
            T(r"$x(s)=x_0+\dfrac{\sin(\theta_0+\kappa s)-\sin\theta_0}{\kappa}$", size=34),
            T(r"$y(s)=y_0-\dfrac{\cos(\theta_0+\kappa s)-\cos\theta_0}{\kappa}$", size=34)).arrange(DOWN, buff=0.3)
        formulas.move_to(RIGHT * 3.4 + DOWN * 0.4)
        self.play(FadeOut(meaning), FadeOut(axes), FadeOut(graph), FadeOut(mark), FadeOut(x_label), FadeOut(y_label))
        self.play(Write(formulas))
        self.say("This is the ", ("piecewise constant curvature", YELLOW), " model: one arc per bending section.", where=DOWN * 3.3)
        self.wait(1.5)


class S04Tendon(Explainer):
    """Pull the tendon, the arc bends: tendon length tells the curvature."""

    def construct(self):
        self.title_card("Why an arc? What the tendon does")
        base = np.array([-3.0, -2.3, 0.0])
        length = 3.8
        kappa = ValueTracker(0.0)
        d = 0.35

        def back():
            return pcc(kappa.get_value() + 1e-4, length, base)

        arm = always_redraw(lambda: line_through(back(), BLUE, 12))
        tendon = always_redraw(lambda: line_through(offset_curve(back(), d), RED, 4))
        self.play(Create(arm), Create(tendon))
        d_brace = DoubleArrow(base + np.array([0, 0.0, 0]), base + np.array([d, 0, 0]), buff=0, color=YELLOW, stroke_width=3,
                              max_tip_length_to_length_ratio=0.5)
        d_label = T(("d", YELLOW), size=30).next_to(d_brace, DOWN, buff=0.12)
        self.play(FadeIn(d_brace), FadeIn(d_label))
        self.wait(1)
        self.say("The string runs ", ("d", YELLOW), " beside the middle line of the arm.")
        self.play(kappa.animate.set_value(0.5), run_time=4)
        self.play(FadeOut(d_brace), FadeOut(d_label))
        self.say("Pull the string: the arm ", "bends toward it.")
        lengths = VGroup(T(r"middle line: $L$", size=34, color=BLUE), T(r"string: $L-\Delta\ell$", size=34, color=RED)).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        lengths.move_to(RIGHT * 3.6 + UP * 1.4)
        self.play(FadeIn(lengths))
        eq1 = T(r"$L-\Delta\ell \;=\; L\,(1-\kappa d)$", size=42).move_to(RIGHT * 3.6 + DOWN * 0.1)
        self.play(Write(eq1))
        self.wait(2)
        eq2 = T(r"$\kappa=\dfrac{\Delta\ell}{d\,L}$", (r"$\;$", WHITE), size=54, color=YELLOW).move_to(RIGHT * 3.6 + DOWN * 1.9)
        self.play(Write(eq2))
        self.say("Pull length and curvature are tied together.", where=UP * 3.4)
        self.say("So the ", ("curvature we measure", YELLOW), " also tells how far the string moved.", where=UP * 3.4)
        self.wait(1)


class S05Gravity(Explainer):
    """Real arms are not perfect arcs: gravity. The Cosserat rod model explains why."""

    def construct(self):
        self.title_card("But a real arm is not a perfect arc", "Gravity bends it too")
        length = 3.8
        weights = [0.0, 3.0, 6.0]
        colors = [GREEN, YELLOW, RED]
        base = np.array([-2.6, -2.4, 0.0])
        curves, curvatures = [], []
        for w in weights:
            xy = shape_models.cosserat_planar_static(1.0, 2.0, 2.6, w, n=100)
            curves.append(np.hstack([xy * length + base[:2], np.zeros((100, 1))]))
            theta = np.unwrap(np.arctan2(np.diff(xy[:, 1]), np.diff(xy[:, 0])))
            curvatures.append(np.gradient(theta, 1.0 / 98))
        drawn = [line_through(c, col, 6) for c, col in zip(curves, colors)]
        self.play(Create(drawn[0]), run_time=1.5)
        tag = T(("no gravity", GREEN), size=28).next_to(drawn[0].get_end(), UP)
        self.play(FadeIn(tag))
        self.wait(1)
        for i in (1, 2):
            self.play(Create(drawn[i]), run_time=1.5)
        self.say("More weight: the tip ", ("sags", RED), " and the bend grows near the base.")
        axes = Axes(x_range=[0, 1, 0.5], y_range=[0, 3, 1], x_length=4.2, y_length=2.8,
                    axis_config={"color": GREY, "include_tip": False, "font_size": 22}).shift(RIGHT * 3.6 + UP * 0.3)
        label = T(("curvature", YELLOW), r"$\;\kappa(s)$ along the arm", size=26, color=GREY).next_to(axes, UP, buff=0.15)
        self.play(FadeIn(axes), FadeIn(label))
        for k, col in zip(curvatures, colors):
            xs = np.linspace(0, 1, len(k) + 1)[:-1] + 0.5 / len(k)
            graph = axes.plot_line_graph(xs[1:-1], k[1:-1], line_color=col, add_vertex_dots=False, stroke_width=5)
            self.play(Create(graph), run_time=1.3)
        self.say("A ", ("constant", GREEN), " curvature is only the no-gravity case.", where=DOWN * 3.3)
        eq = T(r"$EI\,\theta'(s)=m(s)$", size=44).move_to(RIGHT * 3.6 + DOWN * 1.9)
        self.play(Write(eq))
        info = T(r"$m$ = string pull $T\,d$ $-$ weight beyond $s$", size=26, color=GREY).next_to(eq, DOWN, buff=0.3)
        self.play(FadeIn(info))
        self.say(("Cosserat rod", YELLOW), " model: physics of a bending rod. Forces in, shape out.", where=UP * 3.4)
        self.say("It is more exact than one arc, and heavier to compute.", where=UP * 3.4)
        self.wait(1)
