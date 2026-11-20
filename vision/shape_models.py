"""Planar shape models of a tendon-driven continuum arm.

All models work in the arm's bending plane (the x-y plane seen by the camera).
Coordinates: x to the right, y UP, base at the origin, arm starts pointing up
unless a base angle is given. Angles in radians, counter-clockwise positive.
Units: any length unit, as long as you stay consistent.
"""
import numpy as np


def backbone_from_angles(theta, ds, base_xy=(0.0, 0.0)):
    """Integrate tangent angles into backbone points.

    Args:
        theta: Tangent angle at each of N nodes (rad), measured from the +x axis.
        ds: Arc length between nodes.
        base_xy: Position of the first node.

    Returns:
        Array (N, 2) of backbone points.
    """
    theta = np.asarray(theta, dtype=float)
    steps = np.stack([np.cos(theta[:-1]) + np.cos(theta[1:]),
                      np.sin(theta[:-1]) + np.sin(theta[1:])], axis=1) * ds / 2.0
    pts = np.vstack([[0.0, 0.0], np.cumsum(steps, axis=0)])
    return pts + np.asarray(base_xy, dtype=float)


def pcc_points(kappa, length, n=50, base_angle=np.pi / 2, base_xy=(0.0, 0.0)):
    """Backbone of ONE constant-curvature arc (PCC model, one section).

    Args:
        kappa: Curvature (1 / length unit). Positive bends left (counter-clockwise).
        length: Arc length of the section.
        n: Number of points.
        base_angle: Tangent angle at the base (pi/2 = pointing up).
        base_xy: Base position.

    Returns:
        Array (n, 2).
    """
    s = np.linspace(0.0, length, n)
    return backbone_from_angles(base_angle + kappa * s, s[1] - s[0], base_xy)


def poly_curvature_points(coeffs, length, n=50, base_angle=np.pi / 2, base_xy=(0.0, 0.0)):
    """Backbone with curvature k(s) = c0 + c1*u + c2*u^2 ..., u = s / length.

    Constant curvature is the special case coeffs = [kappa]. Use this when
    gravity or friction make the arm bend unevenly.

    Args:
        coeffs: Polynomial coefficients, lowest order first.
        length: Arc length.
        n: Number of points.
        base_angle: Tangent angle at the base.
        base_xy: Base position.

    Returns:
        Array (n, 2).
    """
    s = np.linspace(0.0, length, n)
    u = s / length
    ds = s[1] - s[0]
    k = np.polynomial.polynomial.polyval(u, coeffs)
    theta = base_angle + np.concatenate([[0.0], np.cumsum((k[:-1] + k[1:]) / 2 * ds)])
    return backbone_from_angles(theta, ds, base_xy)


def cosserat_planar_static(length, bending_stiffness, tendon_moment, weight_per_length=0.0,
                           n=100, base_angle=np.pi / 2, base_xy=(0.0, 0.0), iterations=200):
    """Static planar Cosserat (Kirchhoff) rod with a tendon moment and gravity.

    Planar rod, no shear, no stretch. Moment balance along the arm:
        EI * theta'(s) = m(s)
        m(s) = tendon_moment - weight_per_length * integral from s to L of (x(t) - x(s)) dt
    The tendon pulls with tension T at offset d from the backbone, so the
    tendon moment is T * d (same all along when the tendon runs at a constant
    offset and ends at the tip). Gravity points down (-y). Solved by fixed-point
    iteration (each pass uses the shape of the previous pass).

    Args:
        length: Arc length L.
        bending_stiffness: EI (force * length^2).
        tendon_moment: T * d, positive bends left.
        weight_per_length: Weight per unit length (force / length). 0 = no gravity.
        n: Number of nodes.
        base_angle: Tangent angle at the clamped base.
        base_xy: Base position.
        iterations: Max fixed-point passes.

    Returns:
        Array (n, 2) of backbone points.
    """
    ds = length / (n - 1)
    pts = pcc_points(tendon_moment / bending_stiffness, length, n, base_angle, base_xy)
    for _ in range(iterations):
        x = pts[:, 0]
        # integral of (x(t) - x(s)) dt for t in [s, L], trapezoid, computed by suffix sums
        seg = (x[:-1] + x[1:]) / 2 * ds
        suffix_area = np.concatenate([np.cumsum(seg[::-1])[::-1], [0.0]])
        remaining = length - np.arange(n) * ds
        gravity_moment = -weight_per_length * (suffix_area - x * remaining)
        m = tendon_moment + gravity_moment
        curvature = m / bending_stiffness
        theta = base_angle + np.concatenate([[0.0], np.cumsum((curvature[:-1] + curvature[1:]) / 2 * ds)])
        new = backbone_from_angles(theta, ds, base_xy)
        if np.max(np.abs(new - pts)) < 1e-9 * length:
            pts = new
            break
        pts = 0.5 * pts + 0.5 * new
    return pts
