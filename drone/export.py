"""Export: one zip per pendant with STL + 3MF per part, parameters, BOM, print notes."""
import io
import json
import zipfile
import numpy as np
import trimesh

from . import parts as PT
from .params import QUALITY, BED, MATERIALS, CLIENT_ONLY

SPINE_STEPS = [
    "  1  Tap every tube end M4 x 14 deep. Press the heat-set inserts into the four speaker bosses from the flat face.",
    "  2  Deck: screw the peak on from underneath (M4). Seat the struts in the deck sockets, M4 + washer from inside the deck.",
    "  3  Wind an M4 x 30 stud half way into the top of each strut. Drop the pod over the studs, then wind an upper tube",
    "     onto each stud until it seats in the pod boss. The pod floor is now clamped between the two tiers of tube.",
    "  4  Speaker in from below, lead up through the opening. Foam strip on the tray seat, tray down over the tubes, 3 x M3.",
    "  5  Breadboard on the tray. Rod through the crown with a nut and washer on both faces; crown onto the tubes, 3 x M4.",
    "  6  Cable and mic into the dome. Lower the dome over the rod with its key in the pod slot; washer and eye nut on top.",
    "     The pendant hangs from the rod, crown and tubes. The dome carries only itself.",
]
PLAIN_STEPS = [
    "  1  Tap the tube ends M4. Press the heat-set inserts into the four speaker bosses from the flat face.",
    "  2  Deck: screw the peak on from underneath (M4). Struts into the deck sockets, M4 from inside the deck.",
    "  3  Pod: strut tops into the pod sockets, M4 + washer from inside the pod (reach through the speaker opening).",
    "  4  Speaker in from below. Foam strip on the tray seat, screw the tray down. Breadboard on the tray.",
    "  5  Eye bolt, cable and mic in the dome. Lugs into the entry slots, push home, twist, M3 lock screw.",
]


def _tm(m):
    v, f = PT.arrays(m)
    return trimesh.Trimesh(v, f, process=False)


def notes(P, R, name):
    mat = MATERIALS[P["material"]]["label"]
    L = [f"{name}", "DronePendantSpeakerTool - Louis Quek, Constants (WT), Isles Institute, SAW 2027", "",
         f"Material {mat}, 0.4 mm nozzle, 0.2 mm layers, wall {P['wall']:.1f} mm, bed {BED[0]:.0f} x {BED[1]:.0f} x {BED[2]:.0f} mm.",
         "Every part is exported in its print orientation, resting on z = 0.", "", "PARTS"]
    for p in R["printed"]:
        L.append(f"  {p['id']}  {p['name']:<10} {p['title']:<14} {p['size'][0]:.1f} x {p['size'][1]:.1f} x {p['size'][2]:.1f} mm  "
                 f"~{p['grams']} g  {p['orient']}, supports: {p['support']}"
                 + ("" if p["fits"] else "  ** OVER BED **"))
    L += ["", "HARDWARE IN THE MODEL"]
    for _, _, _, hm in R["hw"]:
        L.append(f"  {hm['id']}  {hm['title']:<28} {hm['size']}")
    L += ["", "BILL OF MATERIALS"]
    for item, qty in R["bom"]:
        L.append(f"  {qty:>2} x {item}")
    L += ["", "VALUES"]
    for row in R["derived"]:
        L.append(f"  {row[0]:<24} {row[1]}")
    if R["warnings"]:
        L += ["", "WARNINGS"] + ["  - " + w for w in R["warnings"]]
    L += ["", "ASSEMBLY"] + (SPINE_STEPS if P["spine"] else PLAIN_STEPS)
    L += ["", "Keel: lugs into the entry slots of the deck, push home, twist "
          f"{P['twist']:.0f} degrees, fit the M3 lock screw. The deck seat takes a second tray for a battery later."]
    return "\n".join(L) + "\n"


def write_pendant(z, P, folder, name):
    R = PT.build(P, QUALITY.get(P["quality"], 6))
    scene = trimesh.Scene()
    for pname, m, A, ex, fill in R["parts"]:
        tm = _tm(m)
        b = tm.bounds
        tm.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
        pid = next(p["id"] for p in R["printed"] if p["name"] == pname)
        z.writestr(f"{folder}{name}_{pid}_{pname}.stl", tm.export(file_type="stl"))
        scene.add_geometry(tm, node_name=pname, geom_name=pname)
    try:
        z.writestr(f"{folder}{name}_all_parts.3mf", scene.export(file_type="3mf"))
    except Exception as e:                                    # 3MF needs lxml + networkx
        z.writestr(f"{folder}3mf_skipped.txt", f"3MF export unavailable: {e}\n")
    asm = trimesh.util.concatenate([_tm(PT.xf(m, A)) for _, m, A, _, _ in R["parts"]]
                                   + [_tm(m) for _, m, _, _ in R["hw"]])
    z.writestr(f"{folder}{name}_assembly_reference.stl", asm.export(file_type="stl"))
    state = {k: v for k, v in P.items() if k not in CLIENT_ONLY}
    z.writestr(f"{folder}{name}_parameters.json", json.dumps({"controlGUI": 1, "title": "DronePendantSpeakerTool", "state": state}, indent=1))
    z.writestr(f"{folder}{name}_notes.txt", notes(P, R, name))
    return R


def variant(P, i):
    """Pendant i of a set: a new seed and a seeded size jitter of +-7 %."""
    Q = dict(P)
    Q["seed"] = int(P["seed"]) + i
    if i:
        rng = np.random.default_rng(int(P["seed"]) * 977 + i)
        for k in ("t_w", "t_d", "t_h", "b_w", "b_d", "b_h"):
            Q[k] = round(P[k] * float(rng.uniform(0.93, 1.07)))
        Q["t_facets"] = int(max(0, P["t_facets"] + rng.integers(-2, 3)))
        Q["b_facets"] = int(max(0, P["b_facets"] + rng.integers(-2, 3)))
    return Q


def export_zip(P, name="drone", count=1):
    buf = io.BytesIO()
    errors = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(max(1, int(count))):
            Q = variant(P, i)
            nm = name if count == 1 else f"{name}_{i + 1:02d}"
            try:
                write_pendant(z, Q, "" if count == 1 else nm + "/", nm)
            except PT.BuildError as e:
                errors.append(f"{nm} (seed {Q['seed']}): {e}")
        if errors:
            z.writestr("NOT_BUILT.txt", "\n".join(errors) + "\n")
    return buf.getvalue(), errors
