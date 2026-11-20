"""Shared 3Blue1Brown look for the explainer video: pure black, LaTeX text, fixed colors.

Colors have one meaning each, in every scene:
    BLUE   the arm / its backbone      YELLOW  the key thing in the picture
    TEAL   the mask (what the code      RED     tip, error, things to reject
           thinks is arm)               GREEN   the fitted model
    GREY   helper, secondary
"""
import json
import sys
from pathlib import Path

import numpy as np
from manim import (
    BLACK, DOWN, LEFT, RIGHT, UP, WHITE, FadeIn, FadeOut, ImageMobject, Scene, Tex,
    VGroup, VMobject, Write, config,
)

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
sys.path.insert(0, str(HERE.parents[2] / "vision"))
import shape_models  # noqa: E402

BLUE = "#58C4DD"
TEAL = "#5CD0B3"
YELLOW = "#FFFF00"
RED = "#FC6255"
GREEN = "#83C167"
GREY = "#888888"
WALL = "#D9D3B6"
config.background_color = BLACK
IMG_W, IMG_H = 640, 480


def T(*parts, size=36, color=WHITE):
    """LaTeX text. Each part is a string or a (string, color) pair; colored parts stand out."""
    strings = [p if isinstance(p, str) else p[0] for p in parts]
    mob = Tex(*strings, font_size=size, color=color)
    for part, sub in zip(parts, mob.submobjects):
        if not isinstance(part, str):
            sub.set_color(part[1])
    return mob


def load_info(name):
    """Numbers saved by make_assets.py for the 'straight' or 'bent' frame."""
    return json.loads((ASSETS / f"{name}_info.json").read_text())


def load_stats():
    """Per-frame statistics of the whole recording."""
    return json.loads((ASSETS / "run_stats.json").read_text())


def picture(name, height=4.2):
    """A saved camera picture or stage picture as an image object."""
    return ImageMobject(str(ASSETS / f"{name}.png")).set_height(height)


def px_to_scene(image, x, y):
    """Scene position of the pixel (x, y_down) of an image (640x480 camera picture)."""
    corner = image.get_corner(np.array([-1.0, 1.0, 0.0]))
    return corner + np.array([x / IMG_W * image.width, -y / IMG_H * image.height, 0.0])


def line_through(points, color=BLUE, width=6):
    """Smooth curve through points (N, 3 or N, 2)."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[1] == 2:
        pts = np.hstack([pts, np.zeros((len(pts), 1))])
    mob = VMobject(color=color, stroke_width=width)
    mob.set_points_smoothly(pts)
    return mob


def pcc(kappa, length, base, theta0=np.pi / 2, n=60):
    """Scene points (N, 3) of a constant-curvature arc starting at `base`."""
    xy = shape_models.pcc_points(kappa, length, n, theta0, (0.0, 0.0))
    return np.hstack([xy + np.asarray(base[:2]), np.zeros((n, 1))])


class Explainer(Scene):
    """Base scene: a short caption helper that fades in and out."""

    def say(self, *parts, size=34, where=DOWN * 3.2, hold=None):
        """Show a caption, hold it long enough to read, then fade it out."""
        text = T(*parts, size=size).move_to(where)
        n_chars = sum(len(p if isinstance(p, str) else p[0]) for p in parts)
        self.play(FadeIn(text, shift=UP * 0.15), run_time=0.6)
        self.wait(hold if hold is not None else max(2.0, 0.055 * n_chars))
        self.play(FadeOut(text), run_time=0.4)

    def title_card(self, line_one, line_two=None, hold=3.0):
        """Opening line of a scene (plain words, no slide title bar)."""
        group = VGroup(T(line_one, size=48))
        if line_two:
            group.add(T(line_two, size=34, color=GREY))
        group.arrange(DOWN, buff=0.4)
        self.play(Write(group[0]), run_time=1.2)
        if line_two:
            self.play(FadeIn(group[1]), run_time=0.6)
        self.wait(hold)
        self.play(FadeOut(group), run_time=0.6)
