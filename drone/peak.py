"""Diffuser peak: the cone on the deck under the down-firing speaker.

A closed surface of revolution built as a polar grid, so every control can act on it:
  profile   bell | cone | horn | dome | stepped, raised to the sharpness exponent
  tip       hyperbolic rounding of the apex (height is kept)
  sides     0-2 round, 3+ a polygon in plan; twist turns it from base to tip
  oval      squash in y
  lumps     seeded fBm, same noise as the rocks
  texture   ribs | rings | spiral (scale = spacing in mm) or any rock texture, cut inward
            along the profile normal, faded out at the base edge and the tip

Canonical frame: base on z = 0, apex at (0, 0, h). The base never grows past r,
so the peak stays inside the strut bosses whatever the lumps do.
"""
import math
import numpy as np

from . import form

PROFILES = ("bell", "cone", "horn", "dome", "stepped")
PEAK_TEX = ("none", "match", "ribs", "rings", "spiral", "grain", "strata", "cracks", "pitted", "hammered")


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _g(s, kind, steps):
    """Height fraction 0..1 against radial parameter s (0 = base edge, 1 = axis)."""
    if kind == "cone":
        return s
    if kind == "horn":                                   # exponential horn: flat flare at the foot, steep at the axis
        return np.expm1(3.0 * s) / math.expm1(3.0)
    if kind == "dome":
        return np.sqrt(np.clip(1.0 - (1.0 - s) ** 2, 0.0, 1.0))
    g = 0.5 * (1.0 - np.cos(np.pi * s))                  # bell
    if kind == "stepped":
        n = max(2, int(steps))
        q = g * n
        g = (np.floor(q) + _smooth(0.78, 1.0, q - np.floor(q))) / n
        g = np.minimum(g, 1.0)
    return g


def peak_mesh(P, rp, hp, res=5):
    """Vertices (n,3) and outward triangles (m,3) of the peak."""
    ni = 144 if res <= 5 else (240 if res == 6 else 360)
    nj = 72 if res <= 5 else (120 if res == 6 else 180)
    if P["peak_profile"] == "stepped":
        nj *= 2
    s = np.linspace(0.0, 1.0, nj + 1)[:-1]               # last ring stops short of the axis; the apex closes it
    s_ap = np.append(s, 1.0)

    # ---- profile (r, z) along s, then tip rounding
    def prof(sv):
        z = hp * _g(sv, P["peak_profile"], P["peak_steps"]) ** P["peak_k"]
        c = float(P["peak_tip"])
        if c > 0:
            d = hp - z
            z = hp - (np.sqrt(d * d + c * c) - c) * hp / (math.sqrt(hp * hp + c * c) - c)
        return rp * (1.0 - sv), z

    r, z = prof(s_ap)
    # outward profile normal in the (r, z) plane, from finite differences
    dr, dz = np.gradient(r), np.gradient(z)
    nl = np.hypot(dr, dz) + 1e-12
    nr, nz = dz / nl, -dr / nl
    r, z, nr, nz = r[:-1], z[:-1], nr[:-1], nz[:-1]

    th = np.linspace(0.0, 2 * np.pi, ni, endpoint=False)
    T, S = np.meshgrid(th, s, indexing="xy")             # (nj, ni)
    R = np.repeat(r[:, None], ni, 1)
    Z = np.repeat(z[:, None], ni, 1)
    t = Z / hp                                            # height fraction for twist and fades

    # ---- plan shape: polygon + twist + oval
    n = int(P["peak_sides"])
    tw = np.radians(P["peak_twist"]) * t
    if n >= 3:
        seg = 2 * np.pi / n
        a = np.mod(T - tw, seg) - seg / 2
        R = R * math.cos(math.pi / n) / np.cos(a)
    X, Y = R * np.cos(T), R * np.sin(T)
    Y = Y * P["peak_oval"]

    # ---- lumps (fBm, seeded like the rocks), applied in plan
    if P["peak_namp"] > 0:
        perm, grads = form._tables(int(P["seed"]) + 707)
        p = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]) / rp * P["peak_nscale"]
        k = 1.0 + P["peak_namp"] * form.fbm(p + 13.7, perm, grads, 3).reshape(X.shape)
        X, Y = X * k, Y * k

    # ---- texture: cut inward along the profile normal
    kind, depth, scale = P["peak_tex"], float(P["peak_tex_depth"]), float(P["peak_tex_scale"])
    if kind == "match":
        kind, depth, scale = P["texture"], float(P["tex_depth"]), float(P["tex_scale"])
    if kind != "none" and depth > 0:
        if kind in ("ribs", "spiral"):
            nrib = max(3, int(round(2 * np.pi * rp / scale)))
            ph = nrib * T + (nrib * Z / rp if kind == "spiral" else 0.0)          # spiral: ~45 deg helix at the foot
            disp = -depth * 0.5 * (1.0 - np.cos(ph))
        elif kind == "rings":
            disp = -depth * 0.5 * (1.0 - np.cos(2 * np.pi * Z / scale))
        else:
            v = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
            disp = form.texture(v, kind, depth, scale, int(P["seed"]) + 11).reshape(X.shape)
        Rl = np.hypot(X, Y)
        fade = _smooth(0.0, 0.06, S) * _smooth(depth * 1.5, depth * 4.0 + 3.0, Rl)
        disp = disp * fade
        NR, NZ = nr[:, None], nz[:, None]
        ux, uy = X / np.maximum(Rl, 1e-9), Y / np.maximum(Rl, 1e-9)
        X, Y, Z = X + disp * NR * ux, Y + disp * NR * uy, Z + disp * NZ

    # stay inside the circle the strut bosses allow, base on the bed
    rmax = np.hypot(X, Y).max()
    if rmax > rp:
        X, Y = X * rp / rmax, Y * rp / rmax
    Z[0] = 0.0
    Z = np.clip(Z, 0.0, hp)

    # ---- mesh: bottom centre, rings, apex
    v = np.vstack([[0.0, 0.0, 0.0], np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]), [0.0, 0.0, hp]])
    idx = lambda j, i: 1 + j * ni + (i % ni)
    top = len(v) - 1
    f = []
    i = np.arange(ni)
    f.append(np.column_stack([np.zeros(ni, int), idx(0, i + 1), idx(0, i)]))          # base, facing -z
    for j in range(nj - 1):
        a, b, c, d = idx(j, i), idx(j, i + 1), idx(j + 1, i + 1), idx(j + 1, i)
        f.append(np.column_stack([a, b, c]))
        f.append(np.column_stack([a, c, d]))
    f.append(np.column_stack([idx(nj - 1, i), idx(nj - 1, i + 1), np.full(ni, top)]))
    f = np.vstack(f).astype(np.int64)

    # outward orientation, whatever the twist/oval did
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        f = f[:, ::-1]
    return v, f
