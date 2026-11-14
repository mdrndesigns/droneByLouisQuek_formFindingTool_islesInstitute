"""Parts: turns a parameter state into printable solids, hardware and checks.

Coordinates, canonical rock frame: the flat face (floor / deck) is z = 0, the
rock rises in +z, the hang axis is z. The top rock is used as built. The base
rock is the same construction flipped (x, -y, -z) and dropped by the gap.

Each rock splits at a seam into
    pan : flat face + strut bosses + joint spigot   (prints flat face down)
    cap : the closed end + joint socket             (prints seam down)
Top rock: pan = speaker pod, cap = dome. Base rock: pan = deck, cap = keel.
"""
import math
import numpy as np
import manifold3d as m3

from . import form
from . import peak as PK
from .params import BED, MATERIALS, DRIVERS, BOARDS, EYE, QUALITY, CORE

M = m3.Manifold
BIG = 600.0

# twist-lock (mm)
H_SP = 10.0      # spigot height above seam
LUG_Z = 5.0      # lug underside above seam = bearing ledge thickness in the cap
LUG_H = 4.0
LUG_D = 2.5      # radial projection
LUG_W = 14.0
SPIG_T = 3.2     # spigot wall, 8 x 0.4
LIP = 6.0        # tray seat width
TRAY_T = 3.0
MEM = 3.4       # web membrane, vertical thickness (2.4 mm normal at 45 deg)
RING_T = 5.8    # socket ring wall: slot 3.0 + 2.8 behind it
CROWN_T = 6.0   # crown plate
UP_SOCK = 6.0   # upper-tube socket depth in pod bosses and crown
PAD = 8.0        # conformal thickening at hang point / mic collar
AL_RHO = 2.70


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- primitives
def man(v, f):
    return M(m3.Mesh(vert_properties=np.ascontiguousarray(v, dtype=np.float32),
                     tri_verts=np.ascontiguousarray(f, dtype=np.uint32)))


def arrays(m):
    mesh = m.to_mesh()
    return np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3], np.asarray(mesh.tri_verts, dtype=np.int64)


def cyl(r, z0, z1, x=0.0, y=0.0, seg=48):
    return M.cylinder(z1 - z0, r, r, seg).translate([x, y, z0])


def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def rev(pts, deg=360.0, seg=120):
    a = np.asarray(pts, dtype=float)
    area = 0.5 * np.sum(a[:, 0] * np.roll(a[:, 1], -1) - np.roll(a[:, 0], -1) * a[:, 1])
    if area < 0:
        a = a[::-1]
    return M.revolve(m3.CrossSection([a]), seg, deg)


def rz(m, deg):
    return m.rotate([0.0, 0.0, deg])


def union(ms):
    ms = [m for m in ms if m is not None and not m.is_empty()]
    if not ms:
        return M()
    return ms[0] if len(ms) == 1 else M.batch_boolean(ms, m3.OpType.Add)


def clean(m):
    """Drop zero-volume slivers left where two surfaces touch tangentially."""
    d = m.decompose()
    if len(d) <= 1:
        return m
    keep = [b for b in d if b.volume() > 1.0]
    return M.compose(keep) if keep else m


def along(r, length, origin, u, seg=40):
    """Cylinder of radius r starting at origin, running along unit vector u."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    a = np.cross(u, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-6:
        a = np.array([1.0, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(u, a)
    T = np.column_stack([a, b, u, np.asarray(origin, float)])
    return M.cylinder(length, r, r, seg).transform(T)


def xf(m, A):
    return m.transform(np.asarray(A, float)[:3, :4])


def T(x=0.0, y=0.0, z=0.0):
    A = np.eye(4)
    A[:3, 3] = [x, y, z]
    return A


def slice_rho(m, z):
    """Smallest distance from the z axis to the outline of m at height z."""
    best = 1e9
    for p in m.slice(z).to_polygons():
        a = np.asarray(p, float)
        b = np.roll(a, -1, 0)
        ab = b - a
        t = np.clip(-(a * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
        best = min(best, float(np.linalg.norm(a + ab * t[:, None], axis=1).min()))
    return best


def mass_props(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
    vol = vol6.sum() / 6.0
    cen = ((a + b + c) * vol6[:, None]).sum(0) / (24.0 * vol) if abs(vol) > 1e-9 else np.zeros(3)
    return float(vol), cen


def overhang(v, f):
    """Area (cm2) and share of surface steeper than 45 deg, bed contact excluded."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1) / 2.0
    nz = n[:, 2] / np.maximum(2.0 * area, 1e-12)
    zc = (a[:, 2] + b[:, 2] + c[:, 2]) / 3.0
    bad = (nz < -0.7072) & (zc > v[:, 2].min() + 0.3)
    return float(area[bad].sum() / 100.0), float(area[bad].sum() / max(area.sum(), 1e-9))


# ---------------------------------------------------------------- rock core
def rock_spec(P, pre):
    keys = ("w", "d", "h", "cut", "sq", "facets", "facet_depth", "sharp", "namp", "nscale", "taper", "seam")
    s = {k: P[pre + k] for k in keys}
    s["core"] = CORE.get(P[pre + "form"], 1.0)
    s["seed"] = int(P["seed"]) * 2 + (0 if pre == "t_" else 1)
    return s


def core(P, pre, res):
    s = rock_spec(P, pre)
    v, f = form.rock_points(s, res)
    htot = s["h"] * (1.0 - s["cut"])
    off = np.array([0.0, 0.0, s["h"] / 2.0 - s["cut"] * s["h"]])
    # texture is cut into the outside only; the inside skin stays smooth and the full wall stays behind the deepest groove
    depth = min(P["tex_depth"], 3.0) if P["texture"] != "none" else 0.0
    disp = form.texture(v, P["texture"], depth, P["tex_scale"], s["seed"])
    vo = v + (v / np.linalg.norm(v, axis=1)[:, None]) * disp[:, None]
    fl = P["floor"]
    # the seam never drops below what the speaker magnet (top) or the strut bosses (base) need
    need = fl + (P["spk_depth"] + 4.0 + TRAY_T + 3.0 if pre == "t_" else P["socket"] + 15.0)
    zs = round(max(s["seam"] * htot, need), 2)
    O = man(vo + off, f)
    sd = seam_depth_in(P, pre)
    if seam_on(P, pre):
        O = seam_detail(P, O, vo, f, off, zs)
    O = O.trim_by_plane([0, 0, 1.0], 0.0)
    depth = depth + sd                                   # the wall stays full behind the seam detail too
    I = man(form.inset(v, f, P["wall"] + depth) + off, f)
    rho_floor = min(slice_rho(I, fl + 0.5), slice_rho(I, fl + 6.0))
    return {"pre": pre, "s": s, "v": v, "f": f, "off": off, "depth": depth, "htot": htot, "O": O, "I": I, "zs": zs,
            "rho_floor": rho_floor}


# ---------------------------------------------------------------- expressed seam
SEAM_IN = ("groove", "vgroove", "pan_proud")             # styles that cut into the cap or pan skin


def seam_on(P, pre):
    return bool(P["seam_x"]) and P["seam_on"] in ("both", "top" if pre == "t_" else "base")


def seam_depth_in(P, pre):
    if not seam_on(P, pre):
        return 0.0
    return float(P["seam_dep"]) if P["seam_style"] in SEAM_IN else 0.0


def seam_detail(P, O, vo, f, off, zs):
    """Make the split line part of the form: reveal, V-groove, bead, or a step where one half sits proud.
    Exact z slabs against inset / outset copies of the outer skin, so edges are crisp at any mesh resolution."""
    st, w, d = P["seam_style"], float(P["seam_w"]), float(P["seam_dep"])
    skin = lambda t: man(form.inset(vo, f, t) + off, f)           # t > 0 inward, t < 0 outward
    slab = lambda z0, z1: box(-BIG, BIG, -BIG, BIG, z0, z1)
    if st in ("cap_proud", "pan_proud"):
        # the larger half reaches 0.02 mm past the split so the two halves fuse instead of just touching
        if st == "cap_proud":
            return union([O ^ slab(-BIG, zs), skin(-d) ^ slab(zs - 0.02, BIG)])
        return union([skin(d) ^ slab(zs, BIG), O ^ slab(-BIG, zs + 0.02)])
    n, gap = int(P["seam_lines"]), float(P["seam_gap"])
    zc = [zs + (k - (n - 1) / 2.0) * gap for k in range(n)]
    if st == "bead":
        out = skin(-d)
        return union([O] + [out ^ slab(z - w / 2, z + w / 2) for z in zc])
    if st == "groove":
        inn = skin(d)
        bands = union([slab(z - w / 2, z + w / 2) for z in zc])
        return union([O - bands, inn ^ bands])
    # vgroove: 45-degree-ish chamfered sides built as fine terraces, kinder to print than a square reveal
    k = 6
    bands = union([slab(z - w / 2, z + w / 2) for z in zc])
    fill = []
    for i in range(k):
        u0, u1 = -1 + 2 * i / k, -1 + 2 * (i + 1) / k
        di = d * (1.0 - min(abs(u0), abs(u1))) if u0 * u1 >= 0 else d     # depth at the terrace's deepest point
        sk = skin(di) if di > 0.05 else O
        fill += [sk ^ slab(z + u0 * w / 2, z + u1 * w / 2) for z in zc]
    return union([O - bands] + fill)


def joint_radii(C, clr):
    zs = C["zs"]
    rho = min(slice_rho(C["I"], z) for z in (zs - 3.0, zs + 1.0, zs + 5.0, zs + H_SP + 3.0))
    rj = rho - (LUG_D + 1.0)                 # socket bore in the cap
    rb = rj - clr                            # spigot outside
    ra = rb - SPIG_T                         # spigot inside
    return rj, rb, ra, ra - LIP


def crown_z(P, C, rs):
    """Underside of the crown plate: the highest level where it still fits inside the dome."""
    need_r = rs + P["tube_od"] / 2.0 + 4.5 + 1.5
    z = C["htot"] - P["wall"] - C["depth"] - PAD - CROWN_T - 3.0
    while z > C["zs"] + H_SP + 14.0:
        if min(slice_rho(C["I"], z + CROWN_T + 1.0), slice_rho(C["I"], z - UP_SOCK)) >= need_r:
            return math.floor(z)
        z -= 2.0
    return None


def frame_gap(P, x, y):
    """Distance from a strut axis to the speaker frame (rounded square across flats)."""
    h = P["spk_frame"] / 2.0 - 8.0
    dx, dy = max(abs(x) - h, 0.0), max(abs(y) - h, 0.0)
    return math.hypot(dx, dy) - 8.0 if (dx or dy) else -8.0


def build_rock(P, C, kind, strut_xy, clr, hang=(0.0, 0.0), rs=0.0):
    """kind: 'top' | 'base'. Returns parts in canonical coords and facts."""
    O, I, zs, htot, fl = C["O"], C["I"], C["zs"], C["htot"], P["floor"]
    name = "Top rock" if kind == "top" else "Base rock"
    sock = P["socket"]
    boss_r = P["tube_od"] / 2.0 + 4.5
    spine = bool(P["spine"]) and kind == "top"
    boss_h = sock + 5.0 + (UP_SOCK if spine else 0.0)
    n_lug = 1 if spine else int(P["lugs"])          # spine: one key, the dome lifts straight off

    if zs + H_SP + 14.0 > htot - P["wall"]:
        raise BuildError(f"{name}: seam too high for the twist-lock. Lower the seam height.")
    rj, rb, ra, ri = joint_radii(C, clr)
    if ra < 30.0:
        raise BuildError(f"{name}: joint bore is only {2 * ra:.0f} mm. Move the seam to a wider part of the rock.")

    shell = O - I.trim_by_plane([0, 0, 1.0], fl)
    lug0 = 15.0
    lug_ang = [lug0 + i * 360.0 / n_lug for i in range(n_lug)]
    lock_ang = [lug0 + 60.0 + i * 120.0 for i in range(3)]
    lock = bool(P["lock"]) and not spine
    if spine and rs + P["tube_od"] / 2.0 + 1.5 > ra:
        raise BuildError(f"Spine tubes at R{rs:.0f} do not pass the {2 * ra:.0f} mm joint bore. "
                         "Reduce the strut radius or move the seam to a wider part of the top rock.")

    # ---- pan: shell below seam + web / tray seat / spigot in one 45-degree profile
    # underside is one 45-degree line from the wall up to the tray seat, so it prints without support;
    # outside the spigot it is a membrane MEM thick, not a solid wedge
    u0 = zs - TRAY_T - 3.0
    web = rev([(ri, u0), (BIG, u0 - (BIG - ri)), (BIG, u0 + MEM - (BIG - ri)), (rb, u0 + MEM - (rb - ri)),
               (rb, zs + H_SP), (ra, zs + H_SP), (ra, zs - TRAY_T), (ri, zs - TRAY_T)])
    lug = box(rb - 0.6, rb + LUG_D, -LUG_W / 2, LUG_W / 2, zs + LUG_Z, zs + LUG_Z + LUG_H)
    add = [shell.trim_by_plane([0, 0, -1.0], -zs), web ^ O] + [rz(lug, a) for a in lug_ang]
    cut = []
    for (x, y) in strut_xy:
        add.append(cyl(boss_r, 0.0, boss_h, x, y) ^ O)
        cut.append(cyl(P["tube_od"] / 2.0 + 0.2, -1.0, sock, x, y))
        cut.append(cyl(2.25, -1.0, boss_h + 1.0, x, y))                      # M4 clearance
        if spine:
            cut.append(cyl(P["tube_od"] / 2.0 + 0.2, boss_h - UP_SOCK, boss_h + 1.0, x, y))
            if math.hypot(x, y) + P["tube_od"] / 2.0 + 1.0 > ri:             # tube passes through the tray seat: notch it
                cut.append(cyl(P["tube_od"] / 2.0 + 0.6, zs - TRAY_T - 12.0, zs - TRAY_T + 0.5, x, y, 24))
    for a in lock_ang[:3]:                                                   # tray screw pilots, M3 self-tap
        cut.append(rz(cyl(1.3, zs - TRAY_T - 3.5, zs - TRAY_T + 0.5, ra - 3.0, 0.0, 16), a))
    if lock:
        cut.append(rz(along(1.3, SPIG_T + 2.0, [ra - 1.0, 0, zs + 5.5], [1, 0, 0], 16), lock_ang[0]))

    if kind == "top":
        rb_m = P["spk_bcd"] / 2.0
        pilot = 2.2 if P["spk_fix"] == "insert" else 1.3
        for k in range(4):
            a = math.radians(45.0 + 90.0 * k)
            x, y = rb_m * math.cos(a), rb_m * math.sin(a)
            add.append(cyl(4.6, 0.0, fl + 5.5, x, y, 24) ^ O)
            cut.append(cyl(pilot, -1.0, fl + 4.5, x, y, 16))
        cut.append(cyl(P["spk_cut"] / 2.0 + 0.25, -1.0, fl + 8.0, seg=96))
        if P["spk_recess"] > 0:
            cs = m3.CrossSection.square([P["spk_frame"] - 15.6, P["spk_frame"] - 15.6], True).offset(8.0)
            cs = cs ^ m3.CrossSection.circle(rb_m + 5.0, 64)
            cut.append(M.extrude(cs, P["spk_recess"] + 1.0).translate([0, 0, -1.0]))
    elif P["peak"]:
        cut.append(cyl(2.25, -1.0, fl + 1.0))                                # M4 into the peak
    pan = clean(union(add) - union(cut))

    # ---- cap: shell above seam + socket ring with L-slots
    ro = rj + RING_T
    ring = rev([(rj, zs), (ro, zs), (ro, zs + 4.0), (BIG, zs + 4.0 + (BIG - ro)), (BIG, zs + 4.0 + MEM + (BIG - ro)),
                (ro, zs + 4.0 + MEM), (ro, zs + H_SP + 2.0), (rj, zs + H_SP + 2.0)]) ^ O
    s0, s1 = rj - 1.0, rb + LUG_D + 0.5
    half = math.degrees(math.asin((LUG_W / 2.0 + 0.6) / rb))
    run = rev([(s0, zs + LUG_Z - 0.3), (s1, zs + LUG_Z - 0.3), (s1, zs + LUG_Z + LUG_H + 0.4),
               (s0, zs + LUG_Z + LUG_H + 0.4)], deg=P["twist"] + 2 * half, seg=180)
    entry = box(s0, s1, -(LUG_W / 2 + 0.6), LUG_W / 2 + 0.6, zs - 1.0, zs + LUG_Z + LUG_H + 0.4)
    slots = []
    for a in lug_ang:
        if spine:
            slots.append(rz(entry, a))
        else:
            slots.append(rz(run, a - P["twist"] - half))
            slots.append(rz(entry, a - P["twist"]))
    add = [shell.trim_by_plane([0, 0, 1.0], zs), ring - union(slots)]
    cut = []
    if lock:
        cut.append(rz(along(1.7, BIG, [rj - 1.0, 0, zs + 5.5], [1, 0, 0], 16), lock_ang[0]))
        cut.append(rz(along(3.3, BIG, [rj + 4.0, 0, zs + 5.5], [1, 0, 0], 24), lock_ang[0]))

    facts = {"zs": zs, "htot": htot, "rj": rj, "rb": rb, "ra": ra, "ri": ri, "lock_ang": lock_ang, "boss_h": boss_h}
    tray = None
    crown = None
    if kind == "top":
        Ipad = man(form.inset(C["v"], C["f"], P["wall"] + C["depth"] + PAD) + C["off"], C["f"])
        skin = O - Ipad
        hx, hy = hang
        ed = EYE[P["eye"]]
        top_keep = zs + H_SP + 4.0
        add.append((cyl(ed / 2.0 + 16.0, top_keep, htot + 5.0, hx, hy) ^ skin))
        cut.append(cyl(ed / 2.0 + (0.5 if spine else 0.3), top_keep, htot + 5.0, hx, hy, 32))
        cab = (hx + ed / 2.0 + 9.0, hy)                                      # power cable drops beside the rod
        if P["power"]:
            cut.append(cyl(P["cable_d"] / 2.0 + 0.3, top_keep, htot + 5.0, cab[0], cab[1], 24))
            facts["cable"] = cab
        if P["mic"]:
            az, el = math.radians(P["mic_az"]), math.radians(P["mic_el"])
            u = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
            vh = C["v"] / np.linalg.norm(C["v"], axis=1)[:, None]
            k = int(np.argmax(vh @ u))
            exit_pt = C["v"][k] + C["off"]
            if exit_pt[2] < zs + H_SP + P["mic_d"] / 2.0 + 8.0:
                raise BuildError("Mic port lands on the twist-lock. Raise the mic elevation or lower the seam.")
            add.append(along(P["mic_d"] / 2.0 + 2.4, BIG, C["off"], u) ^ skin)
            cut.append(along(P["mic_d"] / 2.0 + 0.1, BIG, C["off"], u, 32))
            facts["mic_pt"], facts["mic_u"] = exit_pt, u
        facts["hang"] = (hx, hy)

        bw, bd, bh = BOARDS[P["board"]]["size"]
        if P["tray"]:
            if bw and math.hypot(bw, bd) / 2.0 + 4.0 > ra - 8.0:
                raise BuildError(f"Breadboard does not fit the {2 * ra:.0f} mm joint bore. "
                                 "Move the seam to a wider part of the rock or pick a smaller board.")
            tp = [cyl(ra - 0.4, zs - TRAY_T, zs, seg=120)]
            tc = [rz(cyl(1.7, zs - TRAY_T - 1.0, zs + 1.0, ra - 3.0, 0.0, 16), a) for a in lock_ang[:3]]
            if bw:
                o, i = 0.3 + 1.6, 0.3
                tp.append(box(-bw / 2 - o, bw / 2 + o, -bd / 2 - o, bd / 2 + o, zs, zs + 2.5)
                          - box(-bw / 2 - i, bw / 2 + i, -bd / 2 - i, bd / 2 + i, zs - 0.01, zs + 3.0)
                          - box(-bw / 4, bw / 4, -bd / 2 - 3.0, bd / 2 + 3.0, zs - 0.01, zs + 3.0))
            tc.append(cyl(4.0, zs - TRAY_T - 1.0, zs + 1.0, 0.0, -min(bd / 2.0 + 10.0, ra - 14.0), 24))   # speaker lead
            if spine:
                tc += [cyl(P["tube_od"] / 2.0 + 0.4, zs - TRAY_T - 1.0, zs + 1.0, x, y, 24) for x, y in strut_xy]
            tray = clean(union(tp) - union(tc))
    cap = clean(union(add) - union(cut))

    if spine:
        # crown tier: the highest level where the plate still fits inside the dome
        zc = crown_z(P, C, rs)
        if zc is None:
            raise BuildError("No room for the crown tier inside the dome. Reduce the strut radius, the taper to crown, "
                             "or lower the seam.")
        hx, hy = hang
        r_c = EYE[P["eye"]] / 2.0 + 9.0 + (P["cable_d"] / 2.0 + 8.0 if P["power"] else 0.0)
        lobes = [cyl(boss_r, zc, zc + CROWN_T, x, y) for x, y in strut_xy] + [cyl(r_c, zc, zc + CROWN_T, hx, hy)]
        plate = M.batch_hull(lobes)
        crown = union([plate] + [cyl(boss_r, zc - UP_SOCK, zc + 0.1, x, y) for x, y in strut_xy])
        cc = [cyl(EYE[P["eye"]] / 2.0 + 0.3, zc - 1.0, zc + CROWN_T + 1.0, hx, hy, 32)]
        for x, y in strut_xy:
            cc.append(cyl(P["tube_od"] / 2.0 + 0.2, zc - UP_SOCK - 1.0, zc, x, y))
            cc.append(cyl(2.25, zc - 1.0, zc + CROWN_T + 1.0, x, y))
        for k in range(3):                                         # cable pass-throughs between the lobes
            a = math.atan2(strut_xy[0][1], strut_xy[0][0]) + math.pi / len(strut_xy) + k * 2 * math.pi / 3
            cc.append(cyl(5.0, zc - 1.0, zc + CROWN_T + 1.0, rs * 0.42 * math.cos(a), rs * 0.42 * math.sin(a), 24))
        if P["power"]:                                             # cable hole under the dome hole + cable-tie slots
            cx, cy = facts["cable"]
            cc.append(cyl(P["cable_d"] / 2.0 + 0.5, zc - 1.0, zc + CROWN_T + 1.0, cx, cy, 24))
            for sgn in (-1.0, 1.0):
                yy = cy + sgn * (P["cable_d"] / 2.0 + 3.5)
                cc.append(box(cx - 2.0, cx + 2.0, yy - 0.9, yy + 0.9, zc - 1.0, zc + CROWN_T + 1.0))
        crown = clean(crown - union(cc))
        facts["zc"] = float(zc)

    chamber = (I.trim_by_plane([0, 0, 1.0], fl).trim_by_plane([0, 0, -1.0], -(zs - TRAY_T)) - pan).volume() / 1e6
    facts["chamber_l"] = chamber
    return {"pan": pan, "cap": cap, "tray": tray, "crown": crown, "facts": facts}


# ---------------------------------------------------------------- hardware (display only)
def hw_speaker(P):
    fr, cutr, dep, mag = P["spk_frame"], P["spk_cut"] / 2.0, P["spk_depth"], P["spk_magnet"] / 2.0
    cs = m3.CrossSection.square([fr - 16.0, fr - 16.0], True).offset(8.0) ^ m3.CrossSection.circle(P["spk_bcd"] / 2 + 5, 64)
    z0 = -1.5 + P["spk_recess"]
    flange = M.extrude(cs, 1.5).translate([0, 0, z0]) - cyl(cutr - 5.0, z0 - 1, z0 + 3)
    mh = min(22.0, dep * 0.45)
    basket = M.cylinder(dep - mh - 1.5, cutr - 1.0, mag * 0.62, 64).translate([0, 0, z0 + 1.5]) \
        - M.cylinder(dep - mh - 6.0, cutr - 3.0, mag * 0.3, 64).translate([0, 0, z0 - 0.5])
    magnet = cyl(mag, z0 + dep - mh, z0 + dep, seg=64)
    return union([flange, basket, magnet])


def hw_eye(P, hx, hy, htot):
    d = EYE[P["eye"]]
    R = d * 1.6
    ring = M.revolve(m3.CrossSection.circle(d * 0.45, 24).translate([R, 0.0]), 48).rotate([90.0, 0, 0])
    return union([cyl(d / 2.0, htot - 16.0, htot + 4.0, 0, 0, 24), ring.translate([0, 0, htot + 4.0 + R])]).translate([hx, hy, 0])


# ---------------------------------------------------------------- assembly
def build(P, res=None):
    res = res or QUALITY["preview"]
    mat = MATERIALS[P["material"]]
    clr = mat["clr"]
    warn = []

    if P["tube_id"] > P["tube_od"] - 1.6:
        raise BuildError("Tube wall under 0.8 mm. Check tube OD / ID.")
    if P["peak"] and P["peak_h"] > P["gap"] - 10.0:
        raise BuildError(f"Peak ({P['peak_h']:.0f}) reaches the speaker. Keep it 10 mm under the gap ({P['gap']:.0f}).")

    Ct, Cb = core(P, "t_", res), core(P, "b_", res)

    # strut circle: inside both flat faces, clear of the speaker frame, and (spine) through the joint and under the crown
    spine = bool(P["spine"])
    boss_r = P["tube_od"] / 2.0 + 4.5
    n = int(P["struts"])
    rot = [math.radians(P["strut_rot"] + i * 360.0 / n) for i in range(n)]
    ring_xy = lambda r: [(r * math.cos(a), r * math.sin(a)) for a in rot]
    clear = lambda r: min(frame_gap(P, x, y) for x, y in ring_xy(r)) >= boss_r + 1.0
    bw, bd, bh = BOARDS[P["board"]]["size"]
    r_max = min(Ct["rho_floor"], Cb["rho_floor"]) - boss_r - 1.0
    why = "the flat faces (raise Flat cut on both rocks for larger faces)"
    if spine:
        r_joint = joint_radii(Ct, clr)[2] - P["tube_od"] / 2.0 - 1.5
        if r_joint < r_max:
            r_max, why = r_joint, "the top joint opening (move the top seam to a wider part of the rock)"
    r_lo = next((r for r in np.arange(P["spk_cut"] / 2.0 + boss_r + 2.0, 200.0, 0.5) if clear(r)), 200.0)
    if P["strut_r"] > 0:
        rs = P["strut_r"]
    else:
        rs = math.floor(r_max * 2.0) / 2.0
        if spine:                                           # step in until the electronics fit under the crown
            want = Ct["zs"] + (bh + 22.0 if bw else 20.0) + UP_SOCK
            while rs - 1.0 >= r_lo and (crown_z(P, Ct, rs) or 0.0) < want:
                rs -= 1.0
    if rs > r_max + 1e-6:
        raise BuildError(f"Strut radius {rs:.1f} mm is outside {why}. Maximum here is {r_max:.1f} mm.")
    if rs < P["spk_cut"] / 2.0 + boss_r + 2.0:
        raise BuildError(f"Strut radius {rs:.1f} mm cuts into the speaker opening (minimum {P['spk_cut'] / 2 + boss_r + 2:.1f} mm): "
                         f"limited by {why}.")
    if not clear(rs):
        warn.append(f"Strut bosses at R{rs:.1f} overlap the speaker frame; R{r_lo:.1f} clears it. Rotate the struts or enlarge the flat faces.")
    xy_top = ring_xy(rs)
    xy_base = [(x, -y) for (x, y) in xy_top]                     # base rock is flipped about X

    lim = rs * 0.35 if spine else 40.0                       # the rod must stay well inside the crown plate
    B = build_rock(P, Cb, "base", xy_base, clr)
    h0 = (0.0, 0.0) if P["auto_cog"] else (float(np.clip(P["hang_x"], -lim, lim)), float(np.clip(P["hang_y"], -lim, lim)))
    Tk = build_rock(P, Ct, "top", xy_top, clr, h0, rs)

    gap = P["gap"]
    A_top = np.eye(4)
    A_base = np.diag([1.0, -1.0, -1.0, 1.0])
    A_base[2, 3] = -gap
    RX = np.diag([1.0, -1.0, -1.0, 1.0])
    tube_a = math.pi * ((P["tube_od"] / 2) ** 2 - (P["tube_id"] / 2) ** 2)

    def assemble(Tk):
        tz, bz = Tk["facts"]["zs"], B["facts"]["zs"]
        parts = [("top_dome", Tk["cap"].translate([0, 0, -tz]), A_top @ T(z=tz), 2.1, 0.9)]
        if Tk["crown"] is not None:
            zt = Tk["facts"]["zc"] + CROWN_T
            parts.append(("crown", Tk["crown"].translate([0, 0, -zt]).rotate([180.0, 0, 0]), A_top @ T(z=zt) @ RX, 1.05, 1.0))
        if Tk["tray"] is not None:
            parts.append(("top_tray", Tk["tray"].translate([0, 0, -(tz - TRAY_T)]), A_top @ T(z=tz - TRAY_T), 0.5, 1.0))
        parts.append(("top_pod", Tk["pan"], A_top, 0.0, 0.9))
        if P["peak"]:
            rp, hp = min(P["peak_r"], rs - boss_r - 1.0), P["peak_h"]   # stays inside the strut bosses
            pk = man(*PK.peak_mesh(P, rp, hp, res))
            if pk.is_empty():
                raise BuildError("Peak did not build as a solid. Ease the texture depth or the lumps.")
            parts.append(("peak", pk - cyl(1.7, -1.0, min(16.0, hp - 6.0), seg=16), T(z=-gap), -0.95, 0.3))
        parts.append(("base_deck", B["pan"], A_base, -1.25, 0.9))
        parts.append(("base_keel", B["cap"].translate([0, 0, -bz]), A_base @ T(z=bz), -2.1, 0.9))
        return parts

    def lengths(Tk):
        F = Tk["facts"]
        L = {"strut": gap + 2 * P["socket"]}
        if spine:
            L["upper"] = F["zc"] - (F["boss_h"] - UP_SOCK)
            L["rod"] = math.ceil((F["htot"] + 22.0 - (F["zc"] - 10.0)) / 5.0) * 5.0
        return L

    def weigh(parts, Tk):
        items, tot, mom = [], 0.0, np.zeros(3)
        for name, m, A, ex, fill in parts:
            v, f = arrays(xf(m, A))
            vol, cen = mass_props(v, f)
            g = vol / 1000.0 * mat["rho"] * fill
            items.append((name, g))
            tot += g
            mom += g * cen
        F, L = Tk["facts"], lengths(Tk)
        drv = DRIVERS.get(P["driver"], {})
        hwm = [(drv.get("spk_mass", 450.0), [0, 0, P["spk_depth"] * 0.6]),
               (tube_a * L["strut"] / 1000.0 * AL_RHO * n, [0, 0, -gap / 2.0]),
               (45.0 if P["board"] != "none" else 0.0, [0, 0, F["zs"] + 8.0]),
               (40.0, [0, 0, F["htot"] * 0.3])]
        if spine:
            ed = EYE[P["eye"]]
            hwm.append((tube_a * L["upper"] / 1000.0 * AL_RHO * n, [0, 0, (F["zc"] + F["boss_h"]) / 2.0]))
            hwm.append((math.pi * (ed / 2) ** 2 * L["rod"] / 1000.0 * 7.85 + 30.0, [F["hang"][0], F["hang"][1], F["htot"]]))
        for g, c in hwm:
            tot += g
            mom += g * np.asarray(c, float)
        return items, tot, mom / tot

    parts = assemble(Tk)
    items, total, cog = weigh(parts, Tk)
    if P["auto_cog"]:
        hx, hy = float(np.clip(cog[0], -lim, lim)), float(np.clip(cog[1], -lim, lim))
        if math.hypot(hx, hy) > 0.3:
            Tk = build_rock(P, Ct, "top", xy_top, clr, (round(hx, 1), round(hy, 1)), rs)
            parts = assemble(Tk)
            items, total, cog = weigh(parts, Tk)
    F, Fb = Tk["facts"], B["facts"]
    hx, hy = F["hang"]
    htot = F["htot"]
    L = lengths(Tk)

    # ---- checks and derived values
    drv = DRIVERS.get(P["driver"], {})
    vb = max(F["chamber_l"] - 0.1 - (n * math.pi * boss_r ** 2 * F["boss_h"]) / 1e6, 0.05)
    derived = []
    derived.append(("hanging mass", f"{total / 1000.0:.2f} kg", "hot"))
    hang_z = htot + 10.0
    tilt = math.degrees(math.atan2(math.hypot(cog[0] - hx, cog[1] - hy), hang_z - cog[2]))
    derived.append(("hang tilt", f"{tilt:.1f} deg", "warn" if tilt > 2.0 else ""))
    if spine:
        derived.append(("load path", f"eye nut > {P['eye'].upper()} rod > crown > {n} tubes > studs > struts > deck", "hot"))
        below = total - items[0][1]
        derived.append(("tension per upper tube", f"{below / 1000.0 * 9.81 / n:.1f} N of ~{0.6 * 60 * tube_a / 4:.0f} N safe"))
        derived.append(("spine cut list", f"{n} x {L['strut']:.0f} + {n} x {L['upper']:.0f} mm tube · rod {L['rod']:.0f} mm", "hot"))
    else:
        derived.append(("load path", "eye bolt > printed dome > twist-lock lugs > pod > struts", "warn"))
        derived.append(("strut cut list", f"{n} x {L['strut']:.0f} mm tube", "hot"))
        warn.append("Spine is off: the whole pendant hangs from printed plastic (dome pad and twist-lock lugs).")
    derived.append(("strut circle", f"R {rs:.1f} mm"))
    derived.append(("speaker chamber", f"{vb:.2f} L"))
    if "qts" in drv:
        k = math.sqrt(1.0 + drv["vas"] / vb)
        derived.append(("sealed Qtc / Fc", f"{drv['qts'] * k:.2f} / {drv['fs'] * k:.0f} Hz"))
        if drv["qts"] * k > 1.1:
            warn.append(f"Chamber {vb:.2f} L gives Qtc {drv['qts'] * k:.2f}: boomy around {drv['fs'] * k:.0f} Hz. Raise the seam or enlarge the top rock.")
    derived.append(("joint bore top / base", f"{2 * F['ra']:.1f} / {2 * Fb['ra']:.1f} mm"))
    if P["peak"]:
        derived.append(("peak", f"R {min(P['peak_r'], rs - boss_r - 1.0):.0f} x {P['peak_h']:.0f}, {gap - P['peak_h']:.0f} mm to speaker"))
    thread = (4.0 - P["tube_id"]) / (2 * 0.5413 * 0.7) * 100.0
    if P["tube_id"] >= 4.0:
        warn.append(f"Tube bore {P['tube_id']:.1f} mm is too large to tap M4.")
    elif not 50.0 <= thread <= 100.0:
        warn.append(f"Tube bore {P['tube_id']:.1f} mm gives {thread:.0f}% M4 thread (aim 55-80%).")
    else:
        derived.append(("M4 thread in tube", f"{thread:.0f}%"))
    head = (F["zc"] - UP_SOCK if spine else htot - P["wall"] - PAD) - F["zs"]
    if bw and head < bh + 22.0:
        warn.append(f"Only {head:.0f} mm between tray and {'crown' if spine else 'dome'}; breadboard + Nano + jumpers want {bh + 22.0:.0f} mm.")
    if bw and spine and P["tray"]:
        for x, y in xy_top:
            dx, dy = max(abs(x) - bw / 2, 0.0), max(abs(y) - bd / 2, 0.0)
            if math.hypot(dx, dy) < P["tube_od"] / 2.0 + 2.0:
                warn.append("A spine tube runs through the breadboard footprint. Rotate the struts or use the mini board.")
                break
    if P["texture"] != "none" and not P.get("detail") and res <= 5:
        warn.append("Texture is shown coarse in this preview. Turn on Fine preview to see it as exported.")

    ORIENT = {"top_dome": "seam down", "base_keel": "seam down", "top_pod": "speaker face down", "crown": "plate down",
              "base_deck": "deck face down", "top_tray": "flat", "peak": "base down"}
    printed = []
    for i, ((name, m, A, ex, fill), (_, g)) in enumerate(zip(parts, items)):
        v, f = arrays(m)
        size = v.max(0) - v.min(0)
        fits = size[2] <= BED[2] and ((size[0] <= BED[0] and size[1] <= BED[1]) or (size[1] <= BED[0] and size[0] <= BED[1]))
        oh_a, oh_p = overhang(v, f)
        support = "none" if oh_a < 3.0 else ("inside roof only" if name in ("top_dome", "base_keel") else "local")
        if not fits:
            warn.append(f"{name} is {size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} mm: over the {BED[0]:.0f} x {BED[1]:.0f} x {BED[2]:.0f} bed.")
        if m.is_empty():
            raise BuildError(f"{name} did not build as a solid.")
        bodies = len(m.decompose())
        if bodies != 1:
            warn.append(f"{name} came out as {bodies} separate bodies.")
        printed.append({"id": f"P{i + 1}", "name": name, "title": TITLE[name], "size": [round(float(x), 1) for x in size],
                        "grams": round(g), "fits": bool(fits), "overhang_cm2": round(oh_a, 1), "overhang_pct": round(oh_p * 100, 1),
                        "orient": ORIENT[name], "support": support, "bodies": bodies, "tris": int(m.num_tri())})

    # ---- hardware for display (true size)
    def tube(z0, z1):
        t = cyl(P["tube_od"] / 2.0, z0, z1, seg=24) - cyl(P["tube_id"] / 2.0, z0 - 1, z1 + 1, seg=16)
        return union([t.translate([x, y, 0]) for x, y in xy_top])

    hw = []
    if spine:
        ed = EYE[P["eye"]]
        z0 = F["zc"] - 10.0
        rod = [cyl(ed / 2.0, z0, z0 + L["rod"], hx, hy, 24),
               cyl(ed * 0.9, F["zc"] - ed * 0.8, F["zc"], hx, hy, 6), cyl(ed * 0.9, F["zc"] + CROWN_T, F["zc"] + CROWN_T + ed * 0.8, hx, hy, 6)]
        zr = htot + 1.5
        ring = M.revolve(m3.CrossSection.circle(ed * 0.45, 24).translate([ed * 1.6, 0.0]), 48).rotate([90.0, 0, 0])
        rod += [cyl(ed * 1.6, htot, zr, hx, hy, 32), cyl(ed * 1.0, zr, zr + ed * 1.2, hx, hy, 24),
                ring.translate([hx, hy, zr + ed * 1.2 + ed * 1.6])]
        hw.append(("rod", "Hang rod + eye nut", f"{P['eye'].upper()} x {L['rod']:.0f}", union(rod), 2.6))
        hw.append(("upper_tubes", "Spine tubes, upper tier", f"{n} x {P['tube_od']:.1f} OD x {L['upper']:.0f}", tube(F["boss_h"] - UP_SOCK, F["zc"]), 0.3))
    else:
        hw.append(("rod", "Eye bolt", P["eye"].upper(), hw_eye(P, hx, hy, htot), 2.6))
    if P["power"]:
        cx, cy = F["cable"]
        z0 = (F["zc"] - 14.0) if spine else htot - P["wall"] - PAD - 14.0
        hw.append(("cable", "Power cable", f"dia {P['cable_d']:.1f}", cyl(P["cable_d"] / 2.0, z0, htot + 70.0, cx, cy, 20), 2.6))
    if bw:
        z = F["zs"]
        e = [box(-bw / 2, bw / 2, -bd / 2, bd / 2, z, z + bh),
             box(-22.5, 22.5, -9, 9, z + bh + 1.0, z + bh + 8.5), box(-27.5, -20.5, -4, 4, z + bh + 2.5, z + bh + 6.5)]
        hw.append(("electronics", "Breadboard + Arduino Nano", f"{bw:.0f} x {bd:.0f} x {bh:.1f}", union(e), 0.62))
    hw.append(("speaker", "Speaker " + drv.get("label", "custom").split(" - ")[0], f"{P['spk_frame']:.0f} sq x {P['spk_depth']:.0f}", hw_speaker(P), -0.45))
    hw.append(("struts", "Struts, gap tier", f"{n} x {P['tube_od']:.1f} OD x {L['strut']:.0f}", tube(-gap - P["socket"], P["socket"]), -0.7))
    hw = [(nm, m, ex, {"id": f"H{i + 1}", "title": ti, "size": sz}) for i, (nm, ti, sz, m, ex) in enumerate(hw)]

    # ---- dimensions, measured on the built solids (world mm)
    world = {nm: arrays(xf(m, A))[0] for nm, m, A, _, _ in parts}
    top = np.vstack([world["top_dome"], world["top_pod"]])
    base = np.vstack([world["base_deck"], world["base_keel"]])
    allv = np.vstack([top, base])
    zt, zb = float(top[:, 2].max()), float(base[:, 2].min())
    xl = float(allv[:, 0].min())
    fm = lambda v: f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"
    dims = []

    def dim(a, b, text=None):
        a, b = [float(x) for x in a], [float(x) for x in b]
        dims.append({"a": a, "b": b, "t": text or fm(float(np.linalg.norm(np.subtract(b, a))))})

    x1, x2, x3 = xl - 22.0, xl - 48.0, xl - 74.0
    tiers = [0.0, F["zs"]] + ([F["zc"], F["zc"] + CROWN_T] if spine else []) + [zt]
    for a, b in zip(tiers[:-1], tiers[1:]):
        dim([x1, 0, a], [x1, 0, b])
    dim([x1, 0, -gap], [x1, 0, 0.0])
    dim([x1, 0, zb], [x1, 0, -gap - Fb["zs"]])
    dim([x1, 0, -gap - Fb["zs"]], [x1, 0, -gap])
    dim([x2, 0, 0.0], [x2, 0, zt])
    dim([x2, 0, zb], [x2, 0, -gap])
    dim([x3, 0, zb], [x3, 0, zt])
    dim([top[:, 0].min(), 0, zt + 22.0], [top[:, 0].max(), 0, zt + 22.0])
    dim([0, top[:, 1].min(), zt + 44.0], [0, top[:, 1].max(), zt + 44.0])
    dim([base[:, 0].min(), 0, zb - 22.0], [base[:, 0].max(), 0, zb - 22.0])
    dim([0, base[:, 1].min(), zb - 44.0], [0, base[:, 1].max(), zb - 44.0])
    sx, sy = xy_top[0]
    dim([0, 0, -gap * 0.5], [sx, sy, -gap * 0.5], "R " + fm(rs))

    bom = bill(P, n, L, spine)
    return {"parts": parts, "hw": hw, "derived": derived, "warnings": list(dict.fromkeys(warn)), "printed": printed, "bom": bom,
            "dims": dims,
            "facts": {"top": {k: v for k, v in F.items() if k in ("zs", "htot", "rj", "rb", "ra", "chamber_l", "zc")},
                      "base": {k: v for k, v in Fb.items() if k in ("zs", "htot", "rj", "rb", "ra")},
                      "strut_r": rs, "lengths": L, "cog": [float(x) for x in cog],
                      "hang": [hx, hy], "mass_g": total, "tilt_deg": tilt}}


TITLE = {"top_dome": "Dome", "crown": "Crown tier", "top_tray": "Tray tier", "top_pod": "Speaker pod",
         "peak": "Diffuser peak", "base_deck": "Deck", "base_keel": "Keel"}


def bill(P, n, L, spine):
    tube = f"Aluminium tube {P['tube_od']:.1f} OD x {P['tube_id']:.1f} ID"
    rows = [(f"{tube}, cut {L['strut']:.0f} mm, tap M4 x 14 deep both ends (gap tier)", n)]
    if spine:
        e = P["eye"].upper()
        rows += [(f"{tube}, cut {L['upper']:.0f} mm, tap M4 x 14 deep both ends (upper tier)", n),
                 ("M4 x 30 threaded stud / grub screw: joins lower and upper tube through each pod boss", n),
                 ("M4 x 16 socket cap screw + washer (crown to upper tubes)", n),
                 ("M4 x 16 socket cap screw + washer (deck to struts, from inside the deck)", n),
                 (f"{e} threaded rod, {L['rod']:.0f} mm", 1),
                 (f"{e} nut + penny washer (above and below the crown plate)", 2),
                 (f"{e} penny washer + {e} lifting eye nut (on top of the dome, clamps it down)", 1)]
    else:
        e = P["eye"].upper()
        rows += [("M4 x 16 socket cap screw + washer (strut ends, from inside pod and deck)", 2 * n),
                 (f"{e} eye bolt, 20 mm shank + {e} nut + penny washer (inside dome)", 1)]
    if P["power"]:
        rows.append((f"Power cable up to {P['cable_d']:.1f} mm dia through dome" + (" and crown; 2.5 mm cable tie as strain relief on the crown" if spine else "; knot or gland inside as strain relief"), 1))
    rows.append(("M3 x 10 pan head (speaker to pod)", 4))
    if P["spk_fix"] == "insert":
        rows.append(("M3 heat-set insert, 4.6 OD x 5.7", 4))
    if P["tray"]:
        rows.append(("M3 x 8 self-tapping (tray to seat) + 3 mm closed-cell foam strip", 3))
    if P["lock"]:
        rows.append(("M3 x 10 self-tapping (twist-lock pin)", 1 if spine else 2))
    if P["peak"]:
        rows.append(("M4 x 16 self-tapping or machine screw (peak, from under the deck)", 1))
    rows.append(("Speaker " + DRIVERS.get(P["driver"], {}).get("label", "custom"), 1))
    return rows


def layout(parts):
    """Print-orientation plate: parts in rows, each resting on z = 0, big parts first."""
    order = sorted(parts, key=lambda p: -(p[1].bounding_box()[3] - p[1].bounding_box()[0]))
    out, x, y, row_d = [], 0.0, 0.0, 0.0
    for name, m, A, ex, fill in order:
        b = m.bounding_box()
        w, d = b[3] - b[0], b[4] - b[1]
        if x > 0 and x + w > 760.0:
            x, y, row_d = 0.0, y - row_d - 120.0, 0.0
        out.append((name, m.translate([x - b[0], y - b[4], -b[2]])))
        x += w + 85.0
        row_d = max(row_d, d)
    return out
