#!/usr/bin/env python3
"""Génère vegah_spatial_standalone.html : dev.html + phrases CRM (mp3, base64) embarquées.

Usage : python3 build_standalone.py --audio ../audio --out vegah_spatial_standalone.html
Les noms attendus sont ceux du corpus (T0_M_Alpha_Bleu_1.mp3). Par défaut : tous les mp3 de <audio>/T0.
"""
import argparse, base64, glob, json, os, re
ap = argparse.ArgumentParser()
ap.add_argument("--audio", default="../audio")
ap.add_argument("--talkers", default="T0")
ap.add_argument("--src", default="dev.html")
ap.add_argument("--out", default="vegah_spatial_standalone.html")
a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, a.src), encoding="utf-8").read()
emb = {}
for t in a.talkers.split(","):
    for f in sorted(glob.glob(os.path.join(here, a.audio, t, "*.mp3"))):
        emb[os.path.basename(f)] = base64.b64encode(open(f, "rb").read()).decode("ascii")
assert emb, "aucun mp3 trouvé"
tag = "<script>\n(function(){"
assert src.count(tag) == 1
out = src.replace(tag, "<script>window.EMBEDDED_AUDIO=" + json.dumps(emb, separators=(",", ":")) + ";</script>\n" + tag)
open(os.path.join(here, a.out), "w", encoding="utf-8").write(out)
print(len(emb), "phrases,", round(os.path.getsize(os.path.join(here, a.out)) / 1e6, 2), "Mo")
