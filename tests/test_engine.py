"""python3 -m tests.test_engine  -  engine checks, no browser needed."""
import io
import json
import zipfile

import numpy as np
import trimesh

from drone import parts, params, export, form


def test_default_builds_single_watertight_bodies():
    R = parts.build(dict(params.DEFAULTS))
    assert not R["warnings"], R["warnings"]
    for name, m, A, ex, fill in R["parts"]:
        v, f = parts.arrays(m)
        tm = trimesh.Trimesh(v, f, process=False)
        assert tm.is_watertight and tm.volume > 0, name
        assert len(m.decompose()) == 1, name
        assert abs(v[:, 2].min()) < 0.05, f"{name} does not sit on the bed"
    assert all(p["fits"] for p in R["printed"])


def test_same_seed_same_rock_any_resolution():
    s = parts.rock_spec(dict(params.DEFAULTS), "t_")
    a, _ = form.rock_points(s, 5)
    b, _ = form.rock_points(s, 6)
    assert np.allclose(a.max(0) - a.min(0), [s["w"], s["d"], s["h"]], rtol=0.02)
    assert np.allclose(b.max(0) - b.min(0), [s["w"], s["d"], s["h"]], rtol=0.02)
    # every coarse vertex has a fine vertex within one coarse edge length: same surface
    d = np.concatenate([np.sqrt(((c[:, None, :] - b[None, :, :]) ** 2).sum(-1)).min(1) for c in np.array_split(a, 64)])
    assert d.max() < 4.0, d.max()


def test_joint_clearances():
    P = dict(params.DEFAULTS)
    R = parts.build(P)
    for k in ("top", "base"):
        F = R["facts"][k]
        assert abs((F["rj"] - F["rb"]) - params.MATERIALS[P["material"]]["clr"]) < 1e-6
    by = {n: (m, A) for n, m, A, _, _ in R["parts"]}
    for a, b in (("top_dome", "top_pod"), ("base_keel", "base_deck"), ("top_tray", "top_pod"), ("peak", "base_deck"),
                 ("crown", "top_dome"), ("crown", "top_tray")):
        hit = parts.xf(*by[a]) ^ parts.xf(*by[b])
        assert hit.volume() < 1.0, f"{a} and {b} overlap by {hit.volume():.1f} mm3 when assembled"


def test_spine_is_continuous_and_clear():
    P = dict(params.DEFAULTS)
    R = parts.build(P)
    world = {n: parts.xf(m, A) for n, m, A, _, _ in R["parts"]}
    hw = {n: m for n, m, _, _ in R["hw"]}
    for h, m in hw.items():                                  # no hardware passes through plastic
        for n, p in world.items():
            assert (m ^ p).volume() < 1.0, f"{h} cuts {n} by {(m ^ p).volume():.1f} mm3"
    L, F = R["facts"]["lengths"], R["facts"]["top"]
    # upper tube runs from the pod boss socket to the crown underside; strut from deck socket to pod socket
    assert abs(L["upper"] - (F["zc"] - (P["socket"] + 5.0))) < 1e-6
    assert abs(L["strut"] - (P["gap"] + 2 * P["socket"])) < 1e-6
    ub = hw["upper_tubes"].bounding_box()
    sb = hw["struts"].bounding_box()
    assert abs((ub[5] - ub[2]) - L["upper"]) < 0.01 and abs((sb[5] - sb[2]) - L["strut"]) < 0.01
    assert ub[2] - sb[5] == 5.0                              # 5 mm of pod boss clamped between the tiers
    # dimensions sent to the screen equal the solids
    top = np.vstack([parts.arrays(world[k])[0] for k in ("top_dome", "top_pod")])
    assert any(abs(float(d["t"]) - (top[:, 0].max() - top[:, 0].min())) < 0.06 for d in R["dims"] if d["t"][0] != "R")


def test_power_cable_toggle():
    on = parts.build(dict(params.DEFAULTS))
    off = parts.build(dict(params.DEFAULTS, power=False))
    crown = lambda R: next(m for n, m, *_ in R["parts"] if n == "crown")
    dome = lambda R: next(m for n, m, *_ in R["parts"] if n == "top_dome")
    assert crown(on).genus() == crown(off).genus() + 3            # cable hole + two tie slots
    assert dome(on).genus() == dome(off).genus() + 1
    assert any(h[0] == "cable" for h in on["hw"]) and not any(h[0] == "cable" for h in off["hw"])


def test_forms_and_textures_build():
    for fm in params.FORMS:
        F = params.FORMS[fm]
        P = dict(params.DEFAULTS, t_form=fm, b_form=fm, seed=2)
        for pre, i in (("t_", 0), ("b_", 1)):
            for k in ("sq", "facets", "facet_depth", "sharp", "namp", "nscale"):
                P[pre + k] = F[k]
            P[pre + "taper"] = F["taper"][i]
        assert all(p["bodies"] == 1 for p in parts.build(P)["printed"]), fm
    base = parts.build(dict(params.DEFAULTS))["printed"][0]["grams"]
    for tx in form.TEXTURES[1:]:
        R = parts.build(dict(params.DEFAULTS, texture=tx, tex_depth=1.2))
        assert all(p["bodies"] == 1 for p in R["printed"]), tx
        assert R["printed"][0]["grams"] >= base * 0.97, f"{tx} thinned the wall"


def test_refusals_are_explained():
    for change, word in (({"t_seam": 0.8}, "seam"), ({"peak_h": 150.0, "gap": 60.0}, "Peak"),
                         ({"strut_r": 140.0}, "Strut"), ({"tube_id": 6.0}, "Tube")):
        P = dict(params.DEFAULTS, **change)
        try:
            parts.build(P)
        except parts.BuildError as e:
            assert word.lower() in str(e).lower()
        else:
            raise AssertionError(f"{change} should be refused")


def test_peak_forms_and_textures_are_single_solids():
    from drone import peak
    cases = [dict(peak_profile=p, peak_tex=t, peak_tex_depth=3.0, peak_tex_scale=6.0)
             for p in peak.PROFILES for t in ("none", "ribs", "spiral", "cracks")]
    cases += [dict(peak_sides=3, peak_twist=180, peak_oval=0.6, peak_namp=0.2, peak_tip=30)]
    for c in cases:
        P = dict(params.DEFAULTS, **c)
        R = parts.build(P)
        m = next(m for name, m, A, ex, fill in R["parts"] if name == "peak")
        v, f = parts.arrays(m)
        tm = trimesh.Trimesh(v, f, process=False)
        assert tm.is_watertight and tm.volume > 0 and len(m.decompose()) == 1, c
        assert abs(v[:, 2].min()) < 0.05 and v[:, 2].max() <= P["peak_h"] + 0.01, c
        assert np.hypot(v[:, 0], v[:, 1]).max() <= P["peak_r"] + 0.01, c


def test_expressed_seam_styles_stay_single_watertight_parts():
    for st in ("groove", "vgroove", "bead", "cap_proud", "pan_proud"):
        for extra in ({}, {"seam_lines": 3, "seam_gap": 8.0, "seam_w": 4.0}):
            P = dict(params.DEFAULTS, seam_x=True, seam_style=st, **extra)
            R = parts.build(P)
            for name, m, A, ex, fill in R["parts"]:
                v, f = parts.arrays(m)
                tm = trimesh.Trimesh(v, f, process=False)
                assert tm.is_watertight and tm.volume > 0 and len(m.decompose()) == 1, (st, extra, name)


def test_query_round_trip_and_clamp():
    q = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in params.DEFAULTS.items()}
    assert params.coerce(q) == params.DEFAULTS
    assert params.coerce({"gap": "9999"})["gap"] == 200


def test_export_set():
    P = dict(params.DEFAULTS, quality="draft")
    data, errors = export.export_zip(P, "t", 2)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not errors and "t_01/t_01_P1_top_dome.stl" in names and "t_02/t_02_all_parts.3mf" in names
    st = json.loads(zipfile.ZipFile(io.BytesIO(data)).read("t_02/t_02_parameters.json"))["state"]
    assert st["seed"] == P["seed"] + 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
