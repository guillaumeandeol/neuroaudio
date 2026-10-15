import os
import random
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vegah_spatial import spatial, corpus
from vegah_spatial.geometry import Geometry

_HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = next((p for p in (os.path.join(_HERE, "..", "corpus_demo"), os.path.join(_HERE, "..", "..", "..", "audio", "T0"))
             if os.path.isdir(p)), "")


def onset_diff(az):
    h = spatial.get_hrtf().at(az)
    return spatial._onset(h[:, 1]) - spatial._onset(h[:, 0])      # >0 : l'oreille droite entend plus tard


class TestSpatial(unittest.TestCase):
    def test_lateralisation(self):
        h = spatial.get_hrtf()
        for az in (30, 60, 90):
            r, l = h.at(az)[:, 1], h.at(az)[:, 0]
            self.assertGreater(np.sqrt((r ** 2).sum()), 1.5 * np.sqrt((l ** 2).sum()), az)   # droite plus forte
            self.assertLess(onset_diff(az), -0.1, az)                                          # et plus précoce
            self.assertGreater(onset_diff(-az), 0.1, -az)                                      # miroir

    def test_itd_ordre_de_grandeur(self):
        itd_ms = abs(onset_diff(90)) / spatial.FS * 1000
        self.assertTrue(0.4 < itd_ms < 0.9, itd_ms)    # ITD humain à 90° ≈ 0,6–0,7 ms

    def test_interpolation(self):
        a, b, m = onset_diff(0), onset_diff(5), onset_diff(2.5)
        self.assertTrue(min(a, b) - 0.05 <= m <= max(a, b) + 0.05, (a, m, b))
        a, b, m = onset_diff(40), onset_diff(45), onset_diff(42.5)
        self.assertTrue(min(a, b) - 0.1 <= m <= max(a, b) + 0.1, (a, m, b))

    def test_wrap(self):
        self.assertEqual(spatial.wrap(190), -170)
        self.assertEqual(spatial.wrap(-180), 180)

    def test_snr_avant_spatialisation(self):
        rng = np.random.default_rng(1)
        t = rng.standard_normal(spatial.FS) * 0.3
        m = rng.standard_normal(spatial.FS) * 0.05
        def power(snr):
            y, _ = spatial.render_trial(t, m, 0, 0, snr_db=snr, master_db=-10)
            return float((y[:, 0] ** 2).mean())
        ratio = power(0) / power(10)                 # (1+1)/(1+0,1)
        self.assertAlmostEqual(ratio, 2 / 1.1, delta=0.15)

    def test_limiteur_et_duree(self):
        t = np.ones(1000) * 0.5
        y, info = spatial.render_trial(t, t, 0, 90, snr_db=0, master_db=10, lead_s=0.1)
        self.assertLessEqual(float(np.abs(y).max()), 0.9801)
        self.assertGreater(info["duration"], 0.1)

    def test_masqueur_boucle_et_avance(self):
        t = np.random.default_rng(2).standard_normal(20000) * 0.1
        m = np.random.default_rng(3).standard_normal(5000) * 0.1
        y1, i1 = spatial.render_trial(t, m, -30, 30, lead_s=0.2, loop_masker=True)
        y2, i2 = spatial.render_trial(t, m, -30, 30, lead_s=0.2, loop_masker=False)
        self.assertGreater(i1["duration"], i2["duration"])


class TestGeometry(unittest.TestCase):
    def test_sym(self):
        g = Geometry()
        g.set_sym(90, "L"); self.assertEqual((g.az_t, g.az_m), (-45, 45))
        g.set_sym(60, "R"); self.assertEqual((g.az_t, g.az_m), (30, -30))
        g.set_sym(180, "L"); self.assertEqual((g.az_t, g.az_m, g.separation), (-90, 90, 180))
        g.set_sym(0); self.assertEqual((g.az_t, g.az_m, g.separation), (0, 0, 0))
        g.set_sym(500); self.assertEqual(g.separation, 180)

    def test_drag(self):
        g = Geometry()
        g.set_az("T", -30); self.assertEqual((g.az_t, g.az_m), (-30, 30))
        g.set_az("M", 70); self.assertEqual((g.az_m, g.az_t, g.separation), (70, -70, 140))
        g.set_az("T", 170); self.assertEqual((g.az_t, g.az_m), (90, -90))     # plafonné à ±90°

    def test_libre_et_retour(self):
        g = Geometry(); g.sym = False
        g.set_az("T", 10); g.set_az("M", -100)
        self.assertEqual((g.az_t, g.az_m, g.separation), (10, -100, 110))
        g.enable_sym(); self.assertEqual((g.az_t, g.az_m), (55, -55))

    def test_mirror(self):
        g = Geometry(); g.mirror(); self.assertEqual((g.az_t, g.az_m), (45, -45))


class TestCorpus(unittest.TestCase):
    def test_nommage_reel(self):
        e = corpus.parse_entry("/x/T5/T5_F_Delta_Rouge_2.wav")
        self.assertEqual((e.talker, e.sex, e.callsign, e.color, e.number, e.ok), ("t5", "F", "delta", "rouge", 2, True))
        e = corpus.parse_entry("/x/Whisky-vert-7.mp3")          # repli
        self.assertEqual((e.callsign, e.color, e.number), ("whisky", "vert", 7))
        self.assertFalse(corpus.parse_entry("/x/note.wav").ok)

    @unittest.skipUnless(os.path.isdir(DEMO), "corpus de démonstration absent")
    def test_demo(self):
        c = corpus.Corpus().load_folder(DEMO)
        self.assertEqual(len(c.ok), 256)
        self.assertEqual(len(c.callsigns()), 8)
        x = c.audio(c.ok[0])
        self.assertTrue(0.5 < len(x) / spatial.FS < 4, len(x))

    def _fake(self):
        c = corpus.Corpus()
        for t, sx in (("T0", "M"), ("T4", "F")):
            for cs in ("Alpha", "Charlie", "Delta"):
                for col in ("Bleu", "Jaune", "Rouge", "Vert"):
                    for n in (1, 2, 3):
                        c.entries.append(corpus.parse_entry(f"/x/{t}/{t}_{sx}_{cs}_{col}_{n}.wav"))
        return c

    def test_tirage_locuteurs(self):
        c = self._fake(); rng = random.Random(0)
        def draw(tt, mm, n=60):
            return {(a.talker, b.talker) for a, b in (corpus.pick_trial(c, "delta", tt, mm, rng) for _ in range(n))}
        self.assertEqual(draw("", "same"), {("t0", "t0"), ("t4", "t4")})
        self.assertEqual(draw("", "diff"), {("t0", "t4"), ("t4", "t0")})
        self.assertEqual(draw("t0", "t4"), {("t0", "t4")})
        self.assertEqual(draw("", ""), {("t0", "t0"), ("t0", "t4"), ("t4", "t0"), ("t4", "t4")})
        for _ in range(60):
            a, b = corpus.pick_trial(c, "delta", "", "same", rng)
            self.assertTrue(a.callsign != b.callsign and a.color != b.color and a.number != b.number)

    def test_tirage_impossible(self):
        c = self._fake()
        with self.assertRaises(corpus.NoTrial):
            corpus.pick_trial(c, "delta", "", "t9")
        with self.assertRaises(corpus.NoTrial):
            corpus.pick_trial(c, "zulu")


if __name__ == "__main__":
    unittest.main(verbosity=1)
