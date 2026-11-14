#!/usr/bin/env python3
"""Rebuild without the browser:  python3 build.py drone_parameters.json [count]"""
import json
import sys
from drone.params import coerce
from drone.export import export_zip

if __name__ == "__main__":
    state = json.load(open(sys.argv[1]))
    state = state.get("state", state)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    data, errors = export_zip(coerce({k: str(v).lower() if isinstance(v, bool) else v for k, v in state.items()}), "drone", count)
    open("drone.zip", "wb").write(data)
    print("drone.zip written", "" if not errors else errors)
