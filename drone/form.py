"""Rock form: a star-shaped radial surface.

r(d) for a unit direction d is a smooth-minimum of
  - a superellipsoid (squareness),
  - a set of random chisel planes (facets),
then modulated by fBm noise (lumps) and narrowed toward the far end (taper).
The surface is normalised so its bounding box is exactly W x D x H.
Everything is seeded: one seed -> one rock, at any mesh resolution.
"""
from functools import lru_cache
import numpy as np
import trimesh


@lru_cache(maxsize=4)
def icosphere(res):
    m = trimesh.creation.icosphere(subdivisions=int(res))
    return np.asarray(m.vertices, dtype=np.float64), np.asarray(m.faces, dtype=np.int64)


def _tables(seed):
    rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
    perm = rng.permutation(256)
    g = rng.normal(size=(256, 3))
    g /= np.linalg.norm(g, axis=1)[:, None]
    return np.concatenate([perm, perm]), g


def _noise(p, perm, grads):
    pi = np.floor(p).astype(np.int64)
    pf = p - pi
    u = pf * pf * pf * (pf * (pf * 6 - 15) + 10)
    out = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                h = perm[(perm[(perm[(pi[:, 0] + dx) & 255] + pi[:, 1] + dy) & 255] + pi[:, 2] + dz) & 255]
                d = pf - np.array([dx, dy, dz])
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out += w * (grads[h] * d).sum(1)
    return out


def fbm(p, perm, grads, octaves):
    out, amp, f = np.zeros(len(p)), 1.0, 1.0
    for _ in range(octaves):
        out += amp * _noise(p * f, perm, grads)
        amp *= 0.5
        f *= 2.03
    return out


def _unit_surface(d, s):
    """Points of the un-normalised rock for unit directions d (n,3)."""
    rng = np.random.default_rng(int(s["seed"]) & 0x7FFFFFFF)
    perm, grads = _tables(int(s["seed"]) + 101)
    p = float(s["sq"])
    q = float(s["sharp"])
    rs = float(s.get("core", 1.0)) * (np.abs(d) ** p).sum(1) ** (-1.0 / p)
    acc = rs ** (-q)
    k = int(s["facets"])
    if k > 0 and s["facet_depth"] > 0:
        i = np.arange(k) + 0.5                                   # Fibonacci sphere + jitter: facets spread evenly
        ph, th = np.arccos(1 - 2 * i / k), np.pi * (1 + 5 ** 0.5) * i
        n = np.column_stack([np.cos(th) * np.sin(ph), np.sin(th) * np.sin(ph), np.cos(ph)])
        n = n + 0.35 * rng.normal(size=(k, 3))
        n /= np.linalg.norm(n, axis=1)[:, None]
        h = 1.0 - float(s["facet_depth"]) * rng.uniform(0.25, 1.0, size=k)
        dn = d @ n.T                                   # (n,k)
        with np.errstate(divide="ignore", invalid="ignore"):
            rk = np.where(dn > 1e-6, h[None, :] / np.maximum(dn, 1e-6), np.inf)
        acc = acc + (rk ** (-q)).sum(1)
    r = acc ** (-1.0 / q)
    off = rng.uniform(0, 50, size=3)
    r = r * (1.0 + float(s["namp"]) * fbm(d * float(s["nscale"]) + off, perm, grads, 3))
    pts = d * r[:, None]
    z = pts[:, 2]
    t = np.clip((z - z.min()) / (z.max() - z.min()), 0.0, 1.0)      # 0 at the flat face end, 1 at the far end
    pts[:, :2] *= (1.0 - float(s["taper"]) * t ** 1.4)[:, None]
    return pts


def rock_points(s, res):
    """Outer surface vertices (centre coords, bbox = W,D,H, centred) and faces."""
    probe, _ = icosphere(4)
    pp = _unit_surface(probe, s)
    lo, hi = pp.min(0), pp.max(0)
    scale = np.array([s["w"], s["d"], s["h"]], dtype=float) / (hi - lo)
    mid = (lo + hi) / 2
    d, f = icosphere(res)
    v = (_unit_surface(d, s) - mid) * scale
    return v, f


def vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for i in range(3):
        np.add.at(n, f[:, i], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def inset(v, f, t):
    """Radial inset that gives ~t true wall: move each vertex toward the centre
    by t / cos(angle between normal and radius). Stays star-shaped, so the inner
    skin can never self-intersect."""
    n = vertex_normals(v, f)
    r = np.linalg.norm(v, axis=1)
    vh = v / r[:, None]
    c = np.clip((n * vh).sum(1), 0.45, 1.0)
    return vh * np.maximum(r - t / c, 2.0)[:, None]


# ---------------------------------------------------------------- surface textures
def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def worley(p, seed):
    """Distances to the nearest and second-nearest feature point of a jittered grid."""
    pi = np.floor(p).astype(np.int64)
    f1 = np.full(len(p), 9.0)
    f2 = np.full(len(p), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = pi + np.array([dx, dy, dz])
                h = (c[:, 0] * 73856093) ^ (c[:, 1] * 19349663) ^ (c[:, 2] * 83492791) ^ (int(seed) * 2654435761)
                j = np.column_stack([((h * m) >> 7) & 1023 for m in (1103515245, 22695477, 134775813)]) / 1023.0
                d = np.linalg.norm(c + j - p, axis=1)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
    return f1, f2


TEXTURES = ("none", "grain", "strata", "cracks", "pitted", "hammered")


def texture(v, kind, depth, scale, seed):
    """Radial displacement in mm (<= 0 is cut into the rock) for surface points v (mm)."""
    if kind == "none" or depth <= 0:
        return np.zeros(len(v))
    perm, grads = _tables(int(seed) + 303)
    if kind == "grain":
        return -depth * np.clip(0.5 + 0.9 * fbm(v / scale, perm, grads, 3), 0.0, 1.0)
    if kind == "strata":
        w = 0.5 * fbm(v / (scale * 5.0), perm, grads, 2)
        return -depth * _smooth(0.45, 0.9, np.sin(2 * np.pi * (v[:, 2] / scale + w)))
    if kind == "cracks":
        cell = scale * 2.5
        warp = np.column_stack([fbm(v / cell + o, perm, grads, 2) for o in (0.0, 17.3, 41.7)])
        f1, f2 = worley(v / cell + 0.35 * warp, seed)
        return -depth * (1.0 - _smooth(0.0, max(1.8, depth * 1.3) / cell, f2 - f1))
    f1, _ = worley(v / scale, seed)
    if kind == "pitted":
        return -depth * (1.0 - _smooth(0.10, 0.34, f1))
    return -depth * np.clip(1.0 - (f1 / 0.8) ** 2, 0.0, 1.0)       # hammered
