#!/usr/bin/env python3
"""python3 run.py [port]  -> opens the tool at http://127.0.0.1:8766"""
import sys
import threading
import webbrowser
from drone.server import serve

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    serve(port)
