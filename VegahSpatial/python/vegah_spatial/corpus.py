"""Lecture du corpus CRM français (noms de fichiers du type T5_F_Delta_Rouge_2.wav) et tirage des essais."""
import os
import random
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .spatial import FS, to_fs

AUDIO_EXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
COLORS = {"bleu": "bleu", "blue": "bleu", "jaune": "jaune", "yellow": "jaune",
          "rouge": "rouge", "red": "rouge", "vert": "vert", "green": "vert"}
COLOR_LIST = ["bleu", "jaune", "rouge", "vert"]
NUMBERS = list(range(1, 9))
_DEFAULT_RX = re.compile(r"^(?P<talker>T\d+)_(?P<sex>[MF])_(?P<callsign>[A-Za-z]+)_(?P<color>[A-Za-z]+)_(?P<number>\d+)$", re.I)
_TALKER_TOKEN = re.compile(r"^(t|spk|speaker|loc|locuteur|talker|f|m|h|p)\d+$", re.I)


@dataclass
class Entry:
    path: str
    name: str
    callsign: Optional[str] = None
    color: Optional[str] = None
    number: Optional[int] = None
    talker: Optional[str] = None
    sex: Optional[str] = None

    @property
    def ok(self):
        return bool(self.callsign and self.color in COLOR_LIST and self.number in NUMBERS)

    def label(self):
        return f"{(self.callsign or '?').capitalize()} {self.color} {self.number}"


def parse_entry(path, regex=None):
    name = os.path.basename(path)
    base = os.path.splitext(name)[0]
    e = Entry(path=path, name=name)
    m = (re.compile(regex, re.I) if regex else _DEFAULT_RX).match(base)
    if m:
        g = m.groupdict()
        e.callsign = (g.get("callsign") or "").lower() or None
        e.color = COLORS.get((g.get("color") or "").lower())
        e.number = int(g["number"]) if g.get("number") else None
        e.talker = (g.get("talker") or "").lower() or None
        e.sex = (g.get("sex") or "").upper() or None
        return e
    if regex:
        return e
    # repli : analyse par mots
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", base) if t]
    ci = -1
    for i, t in enumerate(toks):
        if t.lower() in COLORS:
            e.color, ci = COLORS[t.lower()], i
    if ci >= 0 and ci + 1 < len(toks) and toks[ci + 1].isdigit():
        e.number = int(toks[ci + 1])
    alpha = [t for i, t in enumerate(toks) if re.fullmatch(r"[A-Za-z]{2,}", t) and i != ci and not _TALKER_TOKEN.match(t)]
    if alpha:
        e.callsign = alpha[0].lower()
    tk = next((t for t in toks if _TALKER_TOKEN.match(t)), None)
    if tk:
        e.talker = tk.lower()
    else:
        parent = os.path.basename(os.path.dirname(path))
        e.talker = parent.lower() or None
    sx = re.search(r"(?:^|[_\-\s])([MFmf])(?=[_\-\s])", name)
    if sx:
        e.sex = sx.group(1).upper()
    return e


class Corpus:
    def __init__(self):
        self.entries = []
        self._cache = {}

    def load_folder(self, folder, regex=None):
        paths = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(AUDIO_EXT) and not f.startswith("."):
                    paths.append(os.path.join(root, f))
        paths.sort()
        self.entries = [parse_entry(p, regex) for p in paths]
        self._cache.clear()
        return self

    @property
    def ok(self):
        return [e for e in self.entries if e.ok]

    def callsigns(self):
        out = {}
        for e in self.ok:
            out[e.callsign] = out.get(e.callsign, 0) + 1
        return dict(sorted(out.items()))

    def talkers(self):
        out = {}
        for e in self.ok:
            if e.talker and e.talker not in out:
                out[e.talker] = e.sex
        return dict(sorted(out.items()))

    def audio(self, entry):
        """Signal mono à FS (float64), mis en cache."""
        a = self._cache.get(entry.path)
        if a is None:
            import soundfile as sf
            x, sr = sf.read(entry.path, dtype="float64", always_2d=True)
            x = to_fs(x.mean(axis=1), sr, FS)
            a = np.ascontiguousarray(x)
            self._cache[entry.path] = a
        return a


class NoTrial(Exception):
    pass


def pick_trial(corpus, callsign, target_talker="", masker_mode="diff", rng=random):
    """Tire une cible (indicatif donné) et un masqueur (indicatif, couleur et chiffre différents).

    masker_mode : 'diff' (autre locuteur si possible), 'same' (même locuteur = même voix),
                  '' (tous au hasard) ou un identifiant de locuteur précis (ex. 't4').
    """
    ok = corpus.ok
    targets = [e for e in ok if e.callsign == callsign and (not target_talker or e.talker == target_talker)]
    if not targets:
        raise NoTrial("Aucune phrase pour cet indicatif" + (" et ce locuteur." if target_talker else "."))
    te = rng.choice(targets)
    ms = [e for e in ok if e.callsign != te.callsign and e.color != te.color and e.number != te.number]
    if masker_mode == "diff":
        if te.talker:
            other = [e for e in ms if e.talker != te.talker]
            if other:
                ms = other
    elif masker_mode == "same":
        ms = [e for e in ms if e.talker == te.talker]
    elif masker_mode:
        ms = [e for e in ms if e.talker == masker_mode]
    if not ms:
        raise NoTrial("Aucun masqueur compatible avec ce choix de locuteur "
                      "(indicatif, couleur et chiffre doivent différer de la cible).")
    return te, rng.choice(ms)
