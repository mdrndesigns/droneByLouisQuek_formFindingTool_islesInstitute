"""Defaults, catalogues and the control schema (controlGUI format)."""

BED = (340.0, 320.0, 340.0)          # Bambu Lab H2S build volume, mm

MATERIALS = {                         # density g/cm3, extra clearance per face mm
    "petg":  {"label": "PETG",   "rho": 1.27, "clr": 0.30},
    "absgf": {"label": "ABS-GF", "rho": 1.08, "clr": 0.25},
    "pla":   {"label": "PLA",    "rho": 1.24, "clr": 0.20},
}

# Dayton Audio PC83-8 (manufacturer sheet; T/S from loudspeakerdatabase / speakerboxlite)
DRIVERS = {
    "pc83_8": {"label": "Dayton PC83-8 - 3 in, 8 ohm", "spk_cut": 77.0, "spk_bcd": 92.0, "spk_frame": 83.0,
               "spk_depth": 50.0, "spk_magnet": 70.0, "spk_mass": 450.0,
               "fs": 82.1, "qts": 0.63, "vas": 1.7},
    "custom": {"label": "Custom driver"},
}

BOARDS = {                            # footprint w, d, h mm
    "mini": {"label": "Mini 170", "size": (47.0, 35.0, 9.5)},
    "half": {"label": "Half 400", "size": (82.0, 55.0, 9.5)},
    "none": {"label": "None",     "size": (0.0, 0.0, 0.0)},
}

EYE = {"m5": 5.0, "m6": 6.0, "m8": 8.0}

# starting points for the rock form; they write the sliders, the sliders stay free
FORMS = {
    "polyhedral": {"label": "Polyhedral", "sq": 2.0, "facets": 16, "facet_depth": 0.18, "sharp": 40.0, "namp": 0.0, "nscale": 1.5, "taper": (0.05, 0.45)},
    "conical":    {"label": "Conical",    "sq": 2.3, "facets": 5,  "facet_depth": 0.12, "sharp": 14.0, "namp": 0.03, "nscale": 1.4, "taper": (0.40, 0.70)},
    "rocky":      {"label": "Rocky",      "sq": 3.2, "facets": 12, "facet_depth": 0.22, "sharp": 18.0, "namp": 0.045, "nscale": 1.6, "taper": (0.08, 0.50)},
    "organic":    {"label": "Organic",    "sq": 2.4, "facets": 0,  "facet_depth": 0.0,  "sharp": 8.0,  "namp": 0.11, "nscale": 1.1, "taper": (0.15, 0.40)},
}
CORE = {"polyhedral": 1.4}            # how far the facet planes dominate the underlying superellipsoid

PRESETS = {
    "interactive": {"label": "Interactive - 240",
                    "t_w": 240, "t_d": 225, "t_h": 265, "b_w": 215, "b_d": 200, "b_h": 240,
                    "gap": 95, "peak_h": 62, "peak_r": 50},
    "playback":    {"label": "Playback - 310",
                    "t_w": 310, "t_d": 290, "t_h": 340, "b_w": 280, "b_d": 260, "b_h": 310,
                    "gap": 120, "peak_h": 80, "peak_r": 68},
}

DEFAULTS = {
    "preset": "interactive", "seed": 7,
    # top rock (dome + speaker pod)
    "t_form": "rocky", "t_w": 240.0, "t_d": 225.0, "t_h": 265.0, "t_cut": 0.32, "t_sq": 3.2, "t_facets": 12, "t_facet_depth": 0.22,
    "t_sharp": 18.0, "t_namp": 0.045, "t_nscale": 1.6, "t_taper": 0.08, "t_seam": 0.37,
    # base rock (deck + keel)
    "b_form": "rocky", "b_w": 215.0, "b_d": 200.0, "b_h": 240.0, "b_cut": 0.30, "b_sq": 2.8, "b_facets": 10, "b_facet_depth": 0.24,
    "b_sharp": 18.0, "b_namp": 0.05, "b_nscale": 1.5, "b_taper": 0.5, "b_seam": 0.30,
    # expressed seam: the split line drawn into the form
    "seam_x": False, "seam_style": "groove", "seam_w": 6.0, "seam_dep": 1.6, "seam_lines": 1, "seam_gap": 10.0, "seam_on": "both",
    # surface texture (true mm)
    "texture": "none", "tex_depth": 0.8, "tex_scale": 14.0,
    # gap, struts
    "gap": 95.0, "struts": 3, "strut_r": 0.0, "strut_rot": 90.0, "tube_od": 6.5, "tube_id": 3.5, "socket": 10.0,
    # speaker
    "driver": "pc83_8", "spk_cut": 77.0, "spk_bcd": 92.0, "spk_frame": 83.0, "spk_depth": 50.0, "spk_magnet": 70.0,
    "spk_fix": "insert", "spk_recess": 0.0,
    # diffuser peak
    "peak": True, "peak_h": 62.0, "peak_r": 50.0, "peak_k": 1.0,
    "peak_profile": "bell", "peak_steps": 4, "peak_tip": 0.0, "peak_sides": 0, "peak_twist": 0.0, "peak_oval": 1.0,
    "peak_namp": 0.0, "peak_nscale": 1.5,
    "peak_tex": "none", "peak_tex_depth": 1.0, "peak_tex_scale": 10.0,
    # twist-lock
    "twist": 20.0, "lugs": 3, "lock": True,
    # electronics
    "board": "half", "tray": True, "mic": True, "mic_d": 10.0, "mic_az": 35.0, "mic_el": 48.0,
    # hanging
    "spine": True, "power": True, "cable_d": 6.0, "eye": "m6", "auto_cog": True, "hang_x": 0.0, "hang_y": 0.0,
    # print
    "material": "petg", "wall": 2.4, "floor": 4.0, "quality": "fine",
    # view
    "view": "assembled", "detail": False, "explode": 0.0, "section": False, "hardware": True, "annot": True,
}


def _sl(key, label, lo, hi, step, group, **kw):
    return {"key": key, "type": "slider", "label": label, "min": lo, "max": hi, "step": step, "group": group, **kw}


def _rock(prefix, group, taper_label):
    return [
        {"key": prefix + "form", "type": "seg", "label": "Form", "group": group, "wrap": 2,
         "options": [[k, v["label"]] for k, v in FORMS.items()]},
        _sl(prefix + "w", "Width", 140, 330, 1, group),
        _sl(prefix + "d", "Depth", 140, 315, 1, group),
        _sl(prefix + "h", "Height before cut", 120, 420, 1, group),
        _sl(prefix + "cut", "Flat cut", 0.05, 0.5, 0.01, group),
        _sl(prefix + "sq", "Squareness", 2.0, 8.0, 0.1, group),
        _sl(prefix + "facets", "Facets", 0, 24, 1, group),
        _sl(prefix + "facet_depth", "Facet depth", 0.0, 0.4, 0.01, group),
        _sl(prefix + "sharp", "Edge sharpness", 4, 40, 1, group),
        _sl(prefix + "namp", "Lumps", 0.0, 0.15, 0.005, group),
        _sl(prefix + "nscale", "Lump scale", 0.5, 4.0, 0.1, group),
        _sl(prefix + "taper", taper_label, 0.0, 0.7, 0.01, group),
        _sl(prefix + "seam", "Seam height", 0.15, 0.8, 0.01, group),
    ]


SG = "Seam line"
SON = [{"key": "seam_x", "truthy": True}]
PG = "Diffuser peak (centre cone)"
PON = [{"key": "peak", "truthy": True}]

SCHEMA = (
    [
        {"key": "preset", "type": "seg", "label": "Size", "group": "Pendant",
         "options": [[k, v["label"]] for k, v in PRESETS.items()]},
        {"key": "seed", "type": "number", "label": "Seed", "group": "Pendant", "min": 0, "max": 99999, "step": 1},
        {"key": "reseed", "type": "button", "label": "New rock", "group": "Pendant"},
    ]
    + _rock("t_", "Top rock - dome + speaker pod", "Taper to crown")
    + _rock("b_", "Base rock - deck + keel", "Taper to keel")
    + [
        {"key": "seam_x", "type": "toggle", "label": "Make the seam part of the design", "group": SG},
        {"key": "seam_style", "type": "seg", "label": "Style", "group": SG, "wrap": 3, "show": SON,
         "options": [["groove", "Reveal"], ["vgroove", "V-groove"], ["bead", "Bead"], ["cap_proud", "Cap proud"], ["pan_proud", "Pan proud"]]},
        {"key": "seam_on", "type": "seg", "label": "On", "group": SG, "show": SON,
         "options": [["both", "Both rocks"], ["top", "Top"], ["base", "Base"]]},
        _sl("seam_dep", "Depth / height", 0.4, 4.0, 0.1, SG, show=SON),
        _sl("seam_w", "Width", 1, 24, 0.5, SG, show=SON + [{"key": "seam_style", "in": ["groove", "vgroove", "bead"]}]),
        _sl("seam_lines", "Lines", 1, 3, 1, SG, show=SON + [{"key": "seam_style", "in": ["groove", "vgroove", "bead"]}]),
        _sl("seam_gap", "Line spacing", 3, 40, 0.5, SG, show=SON + [{"key": "seam_style", "in": ["groove", "vgroove", "bead"]}, {"key": "seam_lines", "gt": 1}]),
        {"key": "seam_note", "type": "note", "group": SG, "show": SON,
         "text": "Follows Seam height in each rock. V-groove prints cleanest; a reveal leaves a small ledge on the dome side."},
        {"key": "texture", "type": "seg", "label": "Texture", "group": "Surface texture", "wrap": 3,
         "options": [["none", "None"], ["grain", "Grain"], ["strata", "Strata"], ["cracks", "Cracks"], ["pitted", "Pitted"], ["hammered", "Hammered"]]},
        _sl("tex_depth", "Depth", 0.2, 3.0, 0.1, "Surface texture", show={"key": "texture", "not": ["none"]}),
        _sl("tex_scale", "Scale", 3, 60, 1, "Surface texture", show={"key": "texture", "not": ["none"]}),
        {"key": "detail", "type": "toggle", "label": "Fine preview (slower)", "group": "Surface texture"},

        _sl("gap", "Gap", 50, 200, 1, "Gap - struts"),
        _sl("struts", "Struts", 3, 4, 1, "Gap - struts"),
        _sl("strut_r", "Strut radius (0 = auto)", 0, 140, 1, "Gap - struts"),
        _sl("strut_rot", "Rotation", 0, 120, 1, "Gap - struts"),
        _sl("tube_od", "Tube OD", 4, 12, 0.1, "Gap - struts"),
        _sl("tube_id", "Tube ID", 2, 8, 0.1, "Gap - struts"),
        _sl("socket", "Socket depth", 6, 20, 1, "Gap - struts"),

        {"key": "driver", "type": "select", "label": "Driver", "group": "Speaker",
         "options": [[k, v["label"]] for k, v in DRIVERS.items()]},
        _sl("spk_cut", "Baffle cutout", 40, 160, 0.5, "Speaker"),
        _sl("spk_bcd", "Bolt circle", 50, 180, 0.5, "Speaker"),
        _sl("spk_frame", "Frame across flats", 50, 170, 0.5, "Speaker"),
        _sl("spk_depth", "Depth", 20, 90, 1, "Speaker"),
        _sl("spk_magnet", "Magnet", 30, 120, 1, "Speaker"),
        {"key": "spk_fix", "type": "seg", "label": "M3 fixing", "group": "Speaker",
         "options": [["insert", "Heat insert"], ["tap", "Self-tap"]]},
        _sl("spk_recess", "Flange recess (0 = surface)", 0, 3, 0.1, "Speaker"),

        {"key": "peak", "type": "toggle", "label": "Diffuser peak", "group": PG},
        {"key": "peak_profile", "type": "seg", "label": "Profile", "group": PG, "wrap": 3, "show": PON,
         "options": [["bell", "Bell"], ["cone", "Cone"], ["horn", "Horn"], ["dome", "Dome"], ["stepped", "Stepped"]]},
        _sl("peak_steps", "Steps", 2, 10, 1, PG, show=PON + [{"key": "peak_profile", "eq": "stepped"}]),
        _sl("peak_h", "Height", 20, 150, 1, PG, show=PON),
        _sl("peak_r", "Radius", 25, 110, 1, PG, show=PON),
        _sl("peak_k", "Sharpness", 0.5, 2.5, 0.05, PG, show=PON),
        _sl("peak_tip", "Tip rounding", 0, 30, 0.5, PG, show=PON),
        _sl("peak_sides", "Sides (0 = round)", 0, 12, 1, PG, show=PON),
        _sl("peak_twist", "Twist", -180, 180, 1, PG, show=PON),
        _sl("peak_oval", "Oval", 0.6, 1.0, 0.01, PG, show=PON),
        _sl("peak_namp", "Lumps", 0.0, 0.2, 0.005, PG, show=PON),
        _sl("peak_nscale", "Lump scale", 0.5, 5.0, 0.1, PG, show=PON + [{"key": "peak_namp", "gt": 0}]),
        {"key": "peak_tex", "type": "seg", "label": "Texture", "group": PG, "wrap": 3, "show": PON,
         "options": [["none", "None"], ["match", "As rocks"], ["ribs", "Ribs"], ["rings", "Rings"], ["spiral", "Spiral"],
                     ["grain", "Grain"], ["strata", "Strata"], ["cracks", "Cracks"], ["pitted", "Pitted"], ["hammered", "Hammered"]]},
        _sl("peak_tex_depth", "Texture depth", 0.2, 4.0, 0.1, PG, show=PON + [{"key": "peak_tex", "not": ["none", "match"]}]),
        _sl("peak_tex_scale", "Texture scale (mm)", 3, 60, 0.5, PG, show=PON + [{"key": "peak_tex", "not": ["none", "match"]}]),

        {"key": "tw_note", "type": "note", "group": "Twist-lock",
         "text": "With the spine on, the dome is a cover clamped by the hang rod; the twist-lock holds the keel."},
        _sl("twist", "Twist", 12, 40, 1, "Twist-lock"),
        _sl("lugs", "Lugs", 3, 4, 1, "Twist-lock"),
        {"key": "lock", "type": "toggle", "label": "M3 lock screw", "group": "Twist-lock"},

        {"key": "board", "type": "seg", "label": "Breadboard", "group": "Electronics",
         "options": [[k, v["label"]] for k, v in BOARDS.items()]},
        {"key": "tray", "type": "toggle", "label": "Tray / bulkhead", "group": "Electronics"},
        {"key": "mic", "type": "toggle", "label": "Mic port", "group": "Electronics"},
        _sl("mic_d", "Mic hole", 4, 16, 0.1, "Electronics", show={"key": "mic", "truthy": True}),
        _sl("mic_az", "Mic azimuth", 0, 360, 1, "Electronics", show={"key": "mic", "truthy": True}),
        _sl("mic_el", "Mic elevation", 20, 80, 1, "Electronics", show={"key": "mic", "truthy": True}),

        {"key": "spine", "type": "toggle", "label": "Aluminium spine (tiers)", "group": "Hanging"},
        {"key": "eye", "type": "seg", "label": "Rod + eye", "group": "Hanging",
         "options": [["m5", "M5"], ["m6", "M6"], ["m8", "M8"]]},
        {"key": "power", "type": "toggle", "label": "Power cable at hang point", "group": "Hanging"},
        _sl("cable_d", "Cable diameter", 3, 12, 0.5, "Hanging", show={"key": "power", "truthy": True}),
        {"key": "auto_cog", "type": "toggle", "label": "Hang over centre of gravity", "group": "Hanging"},
        _sl("hang_x", "Hang X", -40, 40, 0.5, "Hanging", show={"key": "auto_cog", "not": ["true"]}),
        _sl("hang_y", "Hang Y", -40, 40, 0.5, "Hanging", show={"key": "auto_cog", "not": ["true"]}),

        {"key": "material", "type": "seg", "label": "Material", "group": "Print",
         "options": [[k, v["label"]] for k, v in MATERIALS.items()]},
        _sl("wall", "Wall", 1.6, 4.8, 0.4, "Print"),
        _sl("floor", "Floor / deck", 3, 8, 0.2, "Print"),
        {"key": "quality", "type": "seg", "label": "Export mesh", "group": "Print",
         "options": [["draft", "Draft"], ["fine", "Fine"], ["ultra", "Ultra"]]},

        {"key": "view", "type": "seg", "label": "View", "group": "View",
         "options": [["assembled", "Assembled"], ["print", "Print parts"]]},
        _sl("explode", "Explode", 0, 1, 0.01, "View", show={"key": "view", "in": ["assembled"]}),
        {"key": "section", "type": "toggle", "label": "Section cut", "group": "View"},
        {"key": "hardware", "type": "toggle", "label": "Show hardware", "group": "View"},
        {"key": "annot", "type": "toggle", "label": "Part IDs + dimensions", "group": "View"},
    ]
)

QUALITY = {"preview": 5, "draft": 5, "fine": 6, "ultra": 7}
CLIENT_ONLY = {"explode", "section", "hardware", "annot", "detail", "view"}


def coerce(query, base=None):
    """Typed state from a query dict of strings, using DEFAULTS' types."""
    p = dict(DEFAULTS if base is None else base)
    for k, v in query.items():
        if k not in DEFAULTS:
            continue
        d = DEFAULTS[k]
        try:
            if isinstance(d, bool):
                p[k] = str(v).lower() in ("true", "1", "yes", "on")
            elif isinstance(d, int):
                p[k] = int(float(v))
            elif isinstance(d, float):
                p[k] = float(v)
            else:
                p[k] = str(v)
        except (TypeError, ValueError):
            pass
    for it in SCHEMA:                      # clamp sliders
        if it["type"] in ("slider", "number") and it["key"] in p:
            p[it["key"]] = min(max(p[it["key"]], it["min"]), it["max"])
    return p
