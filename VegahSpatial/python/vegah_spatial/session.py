"""Journal des essais et export CSV (mêmes colonnes que la version web)."""
import csv
import datetime as dt

from .geometry import sep_of

FIELDS = ["trial", "timestamp", "participant", "mode", "target_talker", "masker_talker",
          "target_file", "target_callsign", "target_color", "target_number",
          "masker_file", "masker_callsign", "masker_color", "masker_number",
          "target_az", "masker_az", "separation", "snr_db",
          "resp_color", "resp_number", "correct", "rt_ms"]


class Log:
    def __init__(self):
        self.rows = []
        self.saved = True

    def add(self, trial, participant, te, me, az_t, az_m, snr_db, resp=None):
        """resp = (couleur, chiffre, correct, tr_ms) ou None pour un essai enchaîné sans réponse."""
        row = {
            "trial": len(self.rows) + 1,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "participant": participant, "mode": "reponse" if resp else "enchaine",
            "target_talker": te.talker or "", "masker_talker": me.talker or "",
            "target_file": te.name, "target_callsign": te.callsign, "target_color": te.color, "target_number": te.number,
            "masker_file": me.name, "masker_callsign": me.callsign, "masker_color": me.color, "masker_number": me.number,
            "target_az": _num(az_t), "masker_az": _num(az_m), "separation": _num(sep_of(az_t, az_m)), "snr_db": _num(snr_db),
            "resp_color": resp[0] if resp else "", "resp_number": resp[1] if resp else "",
            "correct": (1 if resp[2] else 0) if resp else "", "rt_ms": resp[3] if resp else "",
        }
        self.rows.append(row)
        self.saved = False
        return row

    def clear(self):
        self.rows = []
        self.saved = True

    def by_separation(self):
        out = {}
        for r in self.rows:
            if r["correct"] == "":
                continue
            o = out.setdefault(r["separation"], [0, 0])
            o[0] += 1
            o[1] += r["correct"]
        return dict(sorted(out.items()))

    def n_unanswered(self):
        return sum(1 for r in self.rows if r["correct"] == "")

    def save_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
            w.writeheader()
            w.writerows(self.rows)
        self.saved = True


def _num(v):
    v = float(v)
    return int(v) if v == int(v) else round(v, 2)
