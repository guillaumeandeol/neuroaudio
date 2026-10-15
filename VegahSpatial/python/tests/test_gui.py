"""Test de l'interface hors écran (QT_QPA_PLATFORM=offscreen) avec lecture simulée."""
import os
import random
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vegah_spatial.gui import MainWindow
from vegah_spatial.player import DummyPlayer

_HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = next((p for p in (os.path.join(_HERE, "..", "corpus_demo"), os.path.join(_HERE, "..", "..", "..", "audio", "T0"))
             if os.path.isdir(p)), "")
SHOT = os.environ.get("VS_SHOT_DIR")
app = QApplication.instance() or QApplication([])


def wait_until(cond, timeout=15):
    t0 = time.time()
    while not cond():
        QTest.qWait(20)
        if time.time() - t0 > timeout:
            raise AssertionError("délai dépassé")


def correct_answer(w):
    te = w.cur["te"]
    w._answer(te.color, te.number)


class TestGui(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow(DummyPlayer(), rng=random.Random(3))
        self.w.load_corpus(DEMO)
        self.w.show()

    def tearDown(self):
        self.w.log.saved = True
        self.w.close()

    def test_corpus_et_menus(self):
        w = self.w
        self.assertIn("256 reconnus", w.corpus_info.text())
        self.assertEqual(w.callsign.currentData(), "delta")
        self.assertEqual([w.m_talker.itemData(i) for i in range(w.m_talker.count())], ["diff", "same", "", "t0"])
        self.assertEqual(w.m_talker.currentData(), "diff")

    def test_geometrie_interface(self):
        w = self.w
        w.sl.setValue(90); self.assertEqual((w.geo.az_t, w.geo.az_m), (-45, 45))
        w.side.setCurrentIndex(1); self.assertEqual((w.geo.az_t, w.geo.az_m), (45, -45))
        w._preset(180); self.assertEqual((w.geo.az_t, w.geo.az_m), (90, -90))
        # glisser la cible sur le plan
        sp = w.space; sp.resize(380, 380)
        c, R, rr = sp._geom()
        start = sp._pt(w.geo.az_t, R); end = sp._pt(-30, R)
        QTest.mousePress(sp, Qt.LeftButton, Qt.NoModifier, start.toPoint())
        QTest.mouseMove(sp, end.toPoint())
        QTest.mouseRelease(sp, Qt.LeftButton, Qt.NoModifier, end.toPoint())
        self.assertEqual((w.geo.az_t, w.geo.az_m), (-30, 30))
        w.cb_sym.setChecked(False)
        w.sp_t.setValue(10); w.sp_m.setValue(-100)
        self.assertEqual((w.geo.az_t, w.geo.az_m, w.geo.separation), (10, -100, 110))
        w.cb_sym.setChecked(True); self.assertEqual((w.geo.az_t, w.geo.az_m), (55, -55))

    def test_essai_avec_reponse(self):
        w = self.w
        w.sl.setValue(60)
        w.b_play.click()
        wait_until(lambda: w.phase == "answering")
        self.assertTrue(all(b.isEnabled() for b in w.cells.values()))
        self.assertIn("masquée", w.info.text())
        te = w.cur["te"]
        w.cells[(te.color, te.number)].click()
        self.assertEqual(w.phase, "done")
        self.assertIn("Correct", w.fb.text())
        r = w.log.rows[-1]
        self.assertEqual((r["target_az"], r["masker_az"], r["separation"], r["correct"]), (-30, 30, 60, 1))
        self.assertEqual(r["target_talker"], "t0")
        self.assertIn("Delta", w.info.text())
        # mauvaise réponse
        w.b_play.click(); wait_until(lambda: w.phase == "answering")
        te = w.cur["te"]
        bad = next(c for c in ("bleu", "jaune", "rouge", "vert") if c != te.color)
        w.cells[(bad, te.number)].click()
        self.assertIn("Incorrect", w.fb.text())
        self.assertEqual(w.log.rows[-1]["correct"], 0)
        self.assertEqual(w.table.rowCount(), 2)
        self.assertIn("Séparation 60", w.summary.text())

    def test_enchainement(self):
        w = self.w
        w.cb_chain.setChecked(True); w.chain_n.setValue(4); w.gap.setValue(50)
        w.cb_rnd.setChecked(True); w.cb_rnd_side.setChecked(True)
        w.b_play.click()
        wait_until(lambda: len(w.log.rows) == 4 and w.phase == "done", 30)
        self.assertTrue(all(r["mode"] == "enchaine" and r["correct"] == "" for r in w.log.rows))
        self.assertTrue(all(not b.isEnabled() for b in w.cells.values()))
        self.assertIn("4 essai(s) enchaîné(s)", w.summary.text())
        self.assertTrue({r["separation"] for r in w.log.rows} <= {0, 30, 60, 90, 120, 180})
        # illimité puis Stop
        w.chain_n.setValue(0); w.b_play.click()
        wait_until(lambda: len(w.log.rows) >= 6, 30)
        w.b_stop.click(); n = len(w.log.rows); QTest.qWait(400)
        self.assertEqual(len(w.log.rows), n)
        self.assertEqual(w.phase, "done")

    def test_stop_pendant_lecture_et_csv(self):
        w = self.w
        w.b_play.click(); wait_until(lambda: w.phase == "answering")
        correct_answer(w)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_test.csv")
        try:
            w.log.save_csv(path)
            txt = open(path, encoding="utf-8-sig").read().splitlines()
            self.assertTrue(txt[0].startswith("trial;timestamp;participant;mode;target_talker;masker_talker"))
            self.assertEqual(len(txt), 2)
            self.assertIn(";reponse;t0;t0;", txt[1])
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_locuteur_impossible(self):
        w = self.w
        w.m_talker.setCurrentIndex(w.m_talker.findData("t0"))
        w.t_talker.setCurrentIndex(w.t_talker.findData("t0"))
        w.b_play.click(); wait_until(lambda: w.phase == "answering")      # T0 contre T0 : possible
        self.assertEqual((w.cur["te"].talker, w.cur["me"].talker), ("t0", "t0"))

    def test_captures(self):
        if not SHOT:
            self.skipTest("VS_SHOT_DIR non défini")
        w = self.w
        w.resize(1340, 900); w.sl.setValue(90)
        w.pid.setText("P01")
        for i in range(3):
            w.b_play.click(); wait_until(lambda: w.phase == "answering"); correct_answer(w)
        w.b_play.click(); wait_until(lambda: w.phase == "answering")
        QTest.qWait(100)
        w.grab().save(os.path.join(SHOT, "vegahspatial_python.png"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
