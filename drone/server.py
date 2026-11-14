"""Local server: /defaults, /preview.bin, /export. Same contract as the other LAB tools."""
import json
import struct
import traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

import numpy as np

from . import parts as PT, export as EX
from .params import DEFAULTS, SCHEMA, PRESETS, DRIVERS, FORMS, BED, QUALITY, coerce

UI = Path(__file__).resolve().parent.parent / "ui"


def _fm(v):
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def preview_blob(P, view="assembled", detail=False):
    R = PT.build(P, 6 if detail else QUALITY["preview"])
    meta = {p["name"]: p for p in R["printed"]}
    items, dims = [], R["dims"]
    if view == "print":
        dims = []
        for name, m in PT.layout(R["parts"]):
            items.append((name, "part", m, 0.0, meta[name]))
            b = m.bounding_box()                               # x0 y0 z0 x1 y1 z1, measured on the solid
            dims.append({"a": [b[0], b[1] - 10, 0], "b": [b[3], b[1] - 10, 0], "t": _fm(b[3] - b[0])})
            dims.append({"a": [b[3] + 10, b[1], 0], "b": [b[3] + 10, b[4], 0], "t": _fm(b[4] - b[1])})
            dims.append({"a": [b[0] - 10, b[1] - 10, 0], "b": [b[0] - 10, b[1] - 10, b[5]], "t": _fm(b[5] - b[2])})
    else:
        for name, m, A, ex, fill in R["parts"]:
            items.append((name, "part", PT.xf(m, A), ex, meta[name]))
        for name, m, ex, hm in R["hw"]:
            items.append((name, "hw", m, ex, hm))
    head = {"items": [], "derived": R["derived"], "warnings": R["warnings"], "printed": R["printed"],
            "facts": R["facts"], "bed": BED, "dims": dims, "bom": R["bom"]}
    bufs = []
    for name, kind, m, ex, mt in items:
        v, f = PT.arrays(m)
        size = mt["size"] if isinstance(mt["size"], str) else " x ".join(_fm(x) for x in mt["size"])
        head["items"].append({"name": name, "kind": kind, "nv": len(v), "nf": len(f), "ex": ex, "id": mt["id"],
                              "title": mt["title"], "size": size, "grams": mt.get("grams"), "orient": mt.get("orient"),
                              "support": mt.get("support"), "fits": mt.get("fits", True)})
        bufs.append(v.astype("<f4").tobytes())
        bufs.append(f.astype("<u4").tobytes())
    hj = json.dumps(head).encode()
    hj += b" " * (-len(hj) % 4)
    return struct.pack("<I", len(hj)) + hj + b"".join(bufs)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(UI), **kw)

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        q = dict(parse_qsl(u.query))
        try:
            if u.path == "/defaults":
                return self._json(200, {"defaults": DEFAULTS, "catalog": {"schema": SCHEMA, "presets": PRESETS,
                                                                           "drivers": DRIVERS, "forms": FORMS, "bed": BED}})
            if u.path == "/preview.bin":
                return self._send(200, preview_blob(coerce(q), q.get("view", "assembled"), q.get("detail") == "true"),
                                  "application/octet-stream")
            if u.path == "/export":
                name = "".join(c for c in q.get("name", "drone") if c.isalnum() or c in "-_") or "drone"
                data, errors = EX.export_zip(coerce(q), name, int(q.get("count", 1)))
                return self._send(200, data, "application/zip",
                                  {"Content-Disposition": f'attachment; filename="{name}.zip"',
                                   "X-Errors": json.dumps(errors)})
        except PT.BuildError as e:
            return self._json(400, {"errors": [str(e)]})
        except Exception as e:                                  # keep the tool alive, show the reason
            traceback.print_exc()
            return self._json(400, {"errors": [f"Build failed: {type(e).__name__}: {e}"]})
        return super().do_GET()


def serve(port=8766):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"DronePendantSpeakerTool  http://127.0.0.1:{port}")
    srv.serve_forever()
