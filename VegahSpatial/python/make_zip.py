#!/usr/bin/env python3
"""Fabrique VegahSpatial_python.zip : application + corpus de démonstration (phrases T0 du dépôt, ../../audio/T0)."""
import os, sys, zipfile
here = os.path.dirname(os.path.abspath(__file__))
demo = os.path.abspath(os.path.join(here, "..", "..", "audio", "T0"))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "VegahSpatial_python.zip")
skip = {"__pycache__", ".venv", "_tmp_test.csv"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(here):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f in skip or f.endswith((".zip", ".pyc")):
                continue
            p = os.path.join(root, f)
            info = zipfile.ZipInfo.from_file(p, os.path.join("VegahSpatial_python", os.path.relpath(p, here)))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, open(p, "rb").read())
    if os.path.isdir(demo):
        for f in sorted(os.listdir(demo)):
            if f.endswith(".mp3"):
                z.write(os.path.join(demo, f), os.path.join("VegahSpatial_python", "corpus_demo", f))
print(out, round(os.path.getsize(out) / 1e6, 2), "Mo")
