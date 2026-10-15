"""Interface graphique (PySide6) de VegahSpatial — équivalent de la page web développeur."""
import math
import os
import random
import time

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import spatial
from .corpus import COLOR_LIST, NUMBERS, Corpus, NoTrial, pick_trial
from .geometry import Geometry
from .player import make_player
from .session import Log

COL_T, COL_M = QColor("#1f7a4d"), QColor("#c2410c")
RESP_COLORS = {"bleu": ("#2f6fd0", "#ffffff"), "jaune": ("#f2c200", "#222222"),
               "rouge": ("#d63a3a", "#ffffff"), "vert": ("#2e9e4f", "#ffffff")}


# ----------------------------------------------------------------------------- plan des sources
class SpaceWidget(QWidget):
    """Vue du dessus : l'auditeur au centre, la cible (C) et le masqueur (M) sur un même cercle."""
    moved = Signal(str, float)          # source ('T' ou 'M'), angle

    def __init__(self, geo, parent=None):
        super().__init__(parent)
        self.geo = geo
        self.active = "M"
        self._drag = None
        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CrossCursor)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(380, 380)

    def heightForWidth(self, w):
        return w

    def _geom(self):
        s = min(self.width(), self.height())
        c = QPointF(self.width() / 2, self.height() / 2)
        return c, s * 0.33, s * 0.045 + 6        # centre, rayon des sources, rayon des pastilles

    def _pt(self, az, r):
        c, _, _ = self._geom()
        a = math.radians(az)
        return QPointF(c.x() + r * math.sin(a), c.y() - r * math.cos(a))

    def _angle_at(self, pos):
        c, _, _ = self._geom()
        return math.degrees(math.atan2(pos.x() - c.x(), -(pos.y() - c.y())))

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, R, rr = self._geom()
        pal = self.palette()
        ink, mut = pal.color(pal.ColorRole.WindowText), pal.color(pal.ColorRole.PlaceholderText)
        pen = QPen(mut, 1.2, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R, R)
        p.setPen(QPen(mut, 1))
        for a in range(-180, 180, 15):
            major = a % 45 == 0
            p.drawLine(self._pt(a, R + rr + 4), self._pt(a, R + rr + (14 if major else 9)))
        f = QFont(self.font()); f.setPointSizeF(max(7.0, self.font().pointSizeF() * 0.85)); p.setFont(f)
        for a in (0, 45, 90, 135, 180, -135, -90, -45):
            q = self._pt(a, R + rr + 28)
            p.drawText(QRectF(q.x() - 22, q.y() - 9, 44, 18), Qt.AlignCenter, f"{a}°")
        # tête
        p.setPen(QPen(ink, 1.5)); p.setBrush(pal.color(pal.ColorRole.Base))
        p.drawEllipse(c, R * 0.17, R * 0.17)
        p.drawEllipse(QPointF(c.x() - R * 0.17 - 3, c.y()), 3, 6)
        p.drawEllipse(QPointF(c.x() + R * 0.17 + 3, c.y()), 3, 6)
        k = R * 0.17
        p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - k - 9), QPointF(c.x() - 7, c.y() - k + 1), QPointF(c.x() + 7, c.y() - k + 1)]))
        # sources
        for key, az, col, lab in (("T", self.geo.az_t, COL_T, "C"), ("M", self.geo.az_m, COL_M, "M")):
            q = self._pt(az, R)
            p.setPen(QPen(col, 1.5, Qt.DashLine)); p.drawLine(c, q)
            thick = (not self.geo.sym) and self.active == key
            p.setPen(QPen(ink, 4 if thick else 1.5)); p.setBrush(col)
            p.drawEllipse(q, rr, rr)
            p.setPen(Qt.white); f2 = QFont(self.font()); f2.setBold(True); p.setFont(f2)
            p.drawText(QRectF(q.x() - rr, q.y() - rr, 2 * rr, 2 * rr), Qt.AlignCenter, lab)

    def mousePressEvent(self, ev):
        c, R, rr = self._geom()
        pos = ev.position()
        near = {k: math.hypot(pos.x() - self._pt(a, R).x(), pos.y() - self._pt(a, R).y())
                for k, a in (("T", self.geo.az_t), ("M", self.geo.az_m))}
        k = min(near, key=near.get)
        if near[k] <= rr + 6:
            self.active = k
        elif self.geo.sym:
            self.active = "T"
        self._drag = self.active
        self.moved.emit(self._drag, self._angle_at(pos))

    def mouseMoveEvent(self, ev):
        if self._drag:
            self.moved.emit(self._drag, self._angle_at(ev.position()))

    def mouseReleaseEvent(self, _ev):
        self._drag = None


# ----------------------------------------------------------------------------- fenêtre principale
class MainWindow(QMainWindow):
    play_done = Signal(int)

    def __init__(self, player, corpus=None, rng=None):
        super().__init__()
        self.setWindowTitle("VegahSpatial — version développeur (Python)")
        self.resize(1340, 900)
        self.player = player
        self.corpus = corpus or Corpus()
        self.geo = Geometry()
        self.log = Log()
        self.rng = rng or random.Random()
        self.cur = None            # essai en cours : dict
        self.phase = "idle"        # idle | playing | answering | done | gap
        self.chain_run = False
        self.chain_count = 0
        self.token = 0
        self.play_done.connect(self._on_play_done)
        self.gap_timer = QTimer(self, singleShot=True)
        self.gap_timer.timeout.connect(self._chain_next)
        self._build()
        self._refresh_geometry()
        self._set_phase("idle")
        self._refresh_corpus_widgets()

    # ---- construction
    def _build(self):
        split = QSplitter(self)
        split.addWidget(self._scroll(self._left_column()))
        split.addWidget(self._scroll(self._right_column()))
        split.setStretchFactor(0, 0); split.setStretchFactor(1, 1)
        split.setSizes([520, 820])
        self.setCentralWidget(split)

    @staticmethod
    def _scroll(w):
        s = QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame); s.setWidget(w)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return s

    def _left_column(self):
        w = QWidget(); w.setMinimumWidth(430); v = QVBoxLayout(w)
        warn = QLabel("<b>Casque obligatoire.</b> Spatialisation par HRTF KEMAR générique (pas une HRTF individuelle) ; "
                      "niveau acoustique non calibré. Outil de recherche en développement, pas un examen.")
        warn.setWordWrap(True); warn.setStyleSheet("background:#fff7e0;color:#5b4300;border:1px solid #d9a441;border-radius:6px;padding:6px")
        v.addWidget(warn)

        g = QGroupBox("Position des sources (vue du dessus)"); gv = QVBoxLayout(g)
        self.space = SpaceWidget(self.geo); self.space.moved.connect(self._on_drag); self.space.setMinimumHeight(330)
        gv.addWidget(self.space, 1)
        leg = QLabel(f"<span style='color:{COL_T.name()}'>●</span> Cible (C) &nbsp; <span style='color:{COL_M.name()}'>●</span> Masqueur (M)"
                     " &nbsp; · même distance à l'auditeur, constante")
        leg.setAlignment(Qt.AlignCenter); leg.setWordWrap(True); gv.addWidget(leg)
        self.sep_lbl = QLabel(); self.sep_lbl.setAlignment(Qt.AlignCenter); self.sep_lbl.setWordWrap(True); gv.addWidget(self.sep_lbl)

        self.cb_sym = QCheckBox("mode symétrique par rapport au droit devant (0°)"); self.cb_sym.setChecked(True)
        self.cb_sym.toggled.connect(self._on_sym); gv.addWidget(self.cb_sym)
        self.sym_box = QWidget(); sb = QVBoxLayout(self.sym_box); sb.setContentsMargins(0, 0, 0, 0)
        self.sep_title = QLabel(); sb.addWidget(self.sep_title)
        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(0, 180); self.sl.setTickPosition(QSlider.TicksBelow); self.sl.setTickInterval(45)
        self.sl.valueChanged.connect(self._on_slider); sb.addWidget(self.sl)
        sc = QHBoxLayout()
        for t in ("0°", "45°", "90°", "135°", "180°"):
            lb = QLabel(t); lb.setStyleSheet("font-size:10px;color:gray"); sc.addWidget(lb)
            if t != "180°":
                sc.addStretch()
        sb.addLayout(sc)
        self.side = QComboBox(); self.side.addItem("Cible à gauche · masqueur à droite", "L"); self.side.addItem("Cible à droite · masqueur à gauche", "R")
        self.side.currentIndexChanged.connect(self._on_side); sb.addWidget(QLabel("Côté de la cible")); sb.addWidget(self.side)
        pr = QHBoxLayout()
        for s in (0, 30, 60, 90, 120, 180):
            b = QPushButton(f"{s}°"); b.clicked.connect(lambda _=False, s=s: self._preset(s)); pr.addWidget(b)
        sb.addLayout(pr)
        gv.addWidget(self.sym_box)

        self.free_box = QWidget(); fb = QHBoxLayout(self.free_box); fb.setContentsMargins(0, 0, 0, 0)
        self.sp_t = QDoubleSpinBox(); self.sp_m = QDoubleSpinBox()
        for sp in (self.sp_t, self.sp_m):
            sp.setRange(-180, 180); sp.setDecimals(1); sp.setSingleStep(1); sp.setSuffix("°")
        self.sp_t.valueChanged.connect(lambda x: self._on_spin("T", x)); self.sp_m.valueChanged.connect(lambda x: self._on_spin("M", x))
        fb.addWidget(QLabel("Angle cible")); fb.addWidget(self.sp_t); fb.addWidget(QLabel("Angle masqueur")); fb.addWidget(self.sp_m)
        gv.addWidget(self.free_box)
        sn = QHBoxLayout(); sn.addWidget(QLabel("Pas d'accrochage"))
        self.snap = QComboBox()
        for s in (1, 5, 10, 15, 30):
            self.snap.addItem(f"{s}°", s)
        self.snap.setCurrentIndex(1); self.snap.currentIndexChanged.connect(self._on_snap); sn.addWidget(self.snap); sn.addStretch()
        gv.addLayout(sn)
        v.addWidget(g)

        p = QGroupBox("Paramètres de l'essai"); f = QFormLayout(p)
        self.snr = QDoubleSpinBox(); self.snr.setRange(-40, 40); self.snr.setSingleStep(0.5); self.snr.setSuffix(" dB"); self.snr.setValue(0)
        self.lead = QSpinBox(); self.lead.setRange(0, 5000); self.lead.setSingleStep(50); self.lead.setSuffix(" ms")
        self.master = QSlider(Qt.Horizontal); self.master.setRange(-40, 10); self.master.setValue(0)
        self.master_lbl = QLabel(); self.master.valueChanged.connect(self._on_master)
        self.cb_loop = QCheckBox("boucler le masqueur s'il est plus court que la cible"); self.cb_loop.setChecked(True)
        self.cb_hide = QCheckBox("masquer l'identité des phrases avant la réponse"); self.cb_hide.setChecked(True)
        self.t_talker = QComboBox(); self.m_talker = QComboBox()
        self.cb_rnd = QCheckBox("tirer au hasard la distance angulaire (symétrique) ou l'angle du masqueur (libre)")
        self.rnd_list = QLineEdit("0,30,60,90,120,180")
        self.cb_rnd_side = QCheckBox("inverser au hasard gauche/droite à chaque essai")
        self.cb_chain = QCheckBox("enchaîner les essais sans attendre de réponse")
        self.gap = QSpinBox(); self.gap.setRange(0, 20000); self.gap.setSingleStep(100); self.gap.setSuffix(" ms"); self.gap.setValue(1000)
        self.chain_n = QSpinBox(); self.chain_n.setRange(0, 1000); self.chain_n.setSpecialValueText("jusqu'à Stop")
        self.pid = QLineEdit(); self.pid.setMaxLength(20); self.pid.setPlaceholderText("ex. P01")
        f.addRow("SNR cible/masqueur", self.snr); f.addRow("Avance du masqueur", self.lead)
        f.addRow("Niveau général", self.master); f.addRow("", self.master_lbl)
        f.addRow(self.cb_loop); f.addRow(self.cb_hide)
        f.addRow("Locuteur de la cible", self.t_talker); f.addRow("Locuteur du masqueur", self.m_talker)
        self.talker_note = QLabel(); self.talker_note.setWordWrap(True); self.talker_note.setStyleSheet("color:gray;font-size:11px")
        f.addRow(self.talker_note)
        f.addRow(self.cb_rnd); f.addRow("Valeurs possibles (°)", self.rnd_list); f.addRow(self.cb_rnd_side)
        f.addRow(self.cb_chain); f.addRow("Pause entre essais", self.gap); f.addRow("Nombre d'essais", self.chain_n)
        f.addRow("Identifiant participant", self.pid)
        note = QLabel("SNR = niveau RMS de la cible moins celui du masqueur, mesurés sur les signaux d'origine avant "
                      "spatialisation (chaque fichier est d'abord ramené au même RMS).")
        note.setWordWrap(True); note.setStyleSheet("color:gray;font-size:11px"); f.addRow(note)
        v.addWidget(p)
        v.addStretch()
        self._on_master()
        return w

    def _right_column(self):
        w = QWidget(); v = QVBoxLayout(w)
        c = QGroupBox("Corpus"); cv = QVBoxLayout(c)
        row = QHBoxLayout()
        b = QPushButton("Choisir le dossier du corpus…"); b.clicked.connect(self._choose_folder); row.addWidget(b); row.addStretch()
        cv.addLayout(row)
        self.corpus_info = QLabel("Aucun fichier chargé."); self.corpus_info.setWordWrap(True); cv.addWidget(self.corpus_info)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("Indicatif de la cible")); self.callsign = QComboBox(); r2.addWidget(self.callsign, 1); cv.addLayout(r2)
        v.addWidget(c)

        t = QGroupBox("Essai"); tv = QVBoxLayout(t)
        br = QHBoxLayout()
        self.b_play = QPushButton("▶ Nouvel essai"); self.b_play.setDefault(True); self.b_play.clicked.connect(self._new_trial_clicked)
        self.b_replay = QPushButton("↻ Réécouter (angles actuels)"); self.b_replay.clicked.connect(self._replay)
        self.b_stop = QPushButton("■ Stop"); self.b_stop.clicked.connect(self._stop)
        self.b_synth = QPushButton("Test de spatialisation (bruits)"); self.b_synth.clicked.connect(self._synth)
        for b in (self.b_play, self.b_replay, self.b_stop, self.b_synth):
            br.addWidget(b)
        tv.addLayout(br)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setMinimumHeight(24); tv.addWidget(self.status)
        self.info = QLabel(); self.info.setWordWrap(True); tv.addWidget(self.info)
        grid = QGridLayout(); self.cells = {}
        for i, col in enumerate(COLOR_LIST):
            lab = QLabel(col); lab.setStyleSheet("color:gray"); grid.addWidget(lab, i, 0)
            for j, n in enumerate(NUMBERS):
                b = QPushButton(str(n)); b.setFixedSize(46, 40)
                bg, fg = RESP_COLORS[col]
                b.setStyleSheet(f"QPushButton{{background:{bg};color:{fg};font-weight:bold;border:1px solid rgba(0,0,0,.25);border-radius:6px}}"
                                "QPushButton:disabled{opacity:.4;background:#cfd3da;color:#8b909a}")
                b.clicked.connect(lambda _=False, col=col, n=n: self._answer(col, n))
                grid.addWidget(b, i, j + 1); self.cells[(col, n)] = b
        grid.setColumnStretch(len(NUMBERS) + 1, 1)
        tv.addLayout(grid)
        self.fb = QLabel(); self.fb.setStyleSheet("font-weight:bold"); tv.addWidget(self.fb)
        v.addWidget(t)

        r = QGroupBox("Résultats"); rv = QVBoxLayout(r)
        self.summary = QLabel(); self.summary.setWordWrap(True); rv.addWidget(self.summary)
        heads = ["#", "Cible", "Masqueur", "Loc. C", "Loc. M", "Az C", "Az M", "Δ", "SNR", "Réponse", "OK", "TR (ms)"]
        self.table = QTableWidget(0, len(heads)); self.table.setHorizontalHeaderLabels(heads)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.verticalHeader().hide()
        self.table.setMinimumHeight(200); rv.addWidget(self.table, 1)
        rb = QHBoxLayout()
        self.b_csv = QPushButton("Exporter en CSV"); self.b_csv.clicked.connect(self._export_csv)
        self.b_clear = QPushButton("Vider le journal"); self.b_clear.clicked.connect(self._clear_log)
        rb.addWidget(self.b_csv); rb.addWidget(self.b_clear); rb.addStretch(); rv.addLayout(rb)
        hint = QLabel("CSV en UTF-8, séparateur point-virgule. Le temps de réponse est compté depuis la fin de la lecture.")
        hint.setStyleSheet("color:gray;font-size:11px"); rv.addWidget(hint)
        v.addWidget(r, 1)
        return w

    # ---- corpus
    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier du corpus CRM (par ex. 2-Validated-corpus)")
        if d:
            self.load_corpus(d)

    def load_corpus(self, folder):
        self.corpus.load_folder(folder)
        self._refresh_corpus_widgets()

    def _refresh_corpus_widgets(self):
        n_all, n_ok = len(self.corpus.entries), len(self.corpus.ok)
        self.corpus_info.setText(f"{n_all} fichiers audio · {n_ok} reconnus · {n_all - n_ok} non reconnus" if n_all
                                 else "Aucun fichier chargé : choisis le dossier du corpus.")
        prev = self.callsign.currentData()
        self.callsign.clear()
        for k, n in self.corpus.callsigns().items():
            self.callsign.addItem(f"{k.capitalize()} ({n})", k)
        i = self.callsign.findData(prev if prev else "delta")
        if i >= 0:
            self.callsign.setCurrentIndex(i)
        tk = self.corpus.talkers()
        lab = lambda t: t.upper() + (" (homme)" if tk.get(t) == "M" else " (femme)" if tk.get(t) == "F" else "")
        pt, pm = self.t_talker.currentData(), self.m_talker.currentData()
        self.t_talker.clear(); self.m_talker.clear()
        self.t_talker.addItem("tous (au hasard)", "")
        for d, txt in (("diff", "différent de la cible"), ("same", "même que la cible (même voix)"), ("", "tous (au hasard)")):
            self.m_talker.addItem(txt, d)
        for t in tk:
            self.t_talker.addItem(lab(t), t); self.m_talker.addItem(lab(t), t)
        for cb, prev_v, default in ((self.t_talker, pt, ""), (self.m_talker, pm, "diff")):
            i = cb.findData(prev_v if prev_v is not None else default)
            cb.setCurrentIndex(max(i, 0))
        self.talker_note.setText(f"{len(tk)} locuteur{'s' if len(tk) > 1 else ''} dans le corpus chargé : "
                                 + ", ".join(lab(t) for t in tk) + "." if tk else "")

    # ---- géométrie
    def _refresh_geometry(self):
        g = self.geo
        self.sep_lbl.setText(f"Séparation cible–masqueur : <b>{g.separation:g}°</b> · 0° = droit devant, +90° = droite, −90° = gauche, 180° = derrière")
        self.sep_title.setText(f"Distance angulaire cible–masqueur : <b>{g.separation:g}°</b>")
        for w, val in ((self.sl, round(g.separation)),):
            w.blockSignals(True); w.setValue(int(val)); w.blockSignals(False)
        if g.side:
            self.side.blockSignals(True); self.side.setCurrentIndex(0 if g.side == "L" else 1); self.side.blockSignals(False)
        for sp, val in ((self.sp_t, g.az_t), (self.sp_m, g.az_m)):
            sp.blockSignals(True); sp.setValue(val); sp.blockSignals(False)
        self.sym_box.setVisible(g.sym); self.free_box.setVisible(not g.sym)
        self.space.update()

    def _on_drag(self, which, angle):
        self.geo.set_az(which, angle); self._refresh_geometry()

    def _on_sym(self, on):
        if on:
            self.geo.enable_sym()
        else:
            self.geo.sym = False
        self._refresh_geometry()

    def _on_slider(self, v):
        self.geo.set_sym(v, "L" if self.side.currentIndex() == 0 else "R"); self._refresh_geometry()

    def _on_side(self, _i):
        self.geo.set_sym(self.geo.separation, "L" if self.side.currentIndex() == 0 else "R"); self._refresh_geometry()

    def _preset(self, s):
        self.geo.set_sym(s, "L" if self.side.currentIndex() == 0 else "R")
        self._refresh_geometry()

    def _on_spin(self, which, v):
        if not self.geo.sym:
            self.geo.set_az(which, v); self._refresh_geometry()

    def _on_snap(self, _i):
        self.geo.snap = float(self.snap.currentData())
        self.sl.setSingleStep(int(self.geo.snap))
        if self.geo.sym:
            self.geo.set_sym(self.geo.separation, self.geo.side)
        self._refresh_geometry()

    def _on_master(self):
        v = self.master.value()
        self.master_lbl.setText(f"{v} dB · cible ≈ {round(20 * math.log10(spatial.REF_RMS) + v)} dBFS RMS (une limitation évite l'écrêtage)")

    # ---- déroulement
    def _set_phase(self, p):
        self.phase = p
        busy = p in ("playing", "gap")
        self.b_play.setEnabled(not busy)
        self.b_replay.setEnabled(self.cur is not None and not busy)
        self.b_stop.setEnabled(busy)
        for b in self.cells.values():
            b.setEnabled(p == "answering")

    def _say(self, s):
        self.status.setText(s)

    def _new_trial_clicked(self):
        self.chain_run = self.cb_chain.isChecked(); self.chain_count = 0
        self.gap_timer.stop()
        self._new_trial()

    def _new_trial(self):
        cs = self.callsign.currentData()
        if not self.corpus.ok or not cs:
            self.chain_run = False
            self._say("Aucun fichier exploitable : charge le corpus, ou utilise le test de spatialisation.")
            return
        try:
            te, me = pick_trial(self.corpus, cs, self.t_talker.currentData() or "", self.m_talker.currentData(), self.rng)
        except NoTrial as e:
            self.chain_run = False
            self._say(str(e)); return
        if self.cb_rnd.isChecked():
            try:
                vals = [float(x) for x in self.rnd_list.text().replace(";", ",").replace(" ", ",").split(",") if x.strip()]
            except ValueError:
                vals = []
            if vals:
                v = self.rng.choice(vals)
                if self.geo.sym:
                    self.geo.set_sym(abs(v))
                else:
                    self.geo.set_az("M", v)
        if self.cb_rnd_side.isChecked() and self.rng.random() < 0.5:
            self.geo.mirror()
        self._refresh_geometry()
        self.fb.setText(""); self.fb.setStyleSheet("font-weight:bold")
        self._set_phase("playing"); self._say("Décodage…")
        QApplication.processEvents()
        try:
            t, m = self.corpus.audio(te), self.corpus.audio(me)
        except Exception as e:                      # fichier illisible
            self.chain_run = False
            self._set_phase("idle"); self._say(f"Erreur de lecture audio : {e}"); return
        self.cur = {"te": te, "me": me, "t": t, "m": m, "answered": False}
        self._play_current()

    def _play_current(self):
        c = self.cur
        c["az_t"], c["az_m"], c["snr"] = self.geo.az_t, self.geo.az_m, self.snr.value()
        data, info = spatial.render_trial(c["t"], c["m"], c["az_t"], c["az_m"], c["snr"], self.lead.value() / 1000.0,
                                          self.master.value(), self.cb_loop.isChecked())
        self.token += 1
        tok = self.token
        c["chained"] = self.chain_run
        self._set_phase("playing")
        self._say(f"Lecture : cible {c['az_t']:g}°, masqueur {c['az_m']:g}°, SNR {c['snr']:g} dB"
                  + (f" · limitation de {info['limit_db']:.1f} dB" if info["limit_db"] else ""))
        self._update_info()
        try:
            self.player.play(data, spatial.FS, lambda: self.play_done.emit(tok))
        except Exception as e:
            self.chain_run = False
            self._set_phase("done"); self._say(f"Erreur de lecture audio : {e}")

    def _on_play_done(self, tok):
        if tok != self.token or self.cur is None:
            return
        c = self.cur
        if c.get("chained"):
            if not self.chain_run:
                return
            c["answered"] = True
            self.log.add(len(self.log.rows) + 1, self.pid.text().strip(), c["te"], c["me"], c["az_t"], c["az_m"], c["snr"])
            self._update_info(); self._render_log()
            self.chain_count += 1
            n = self.chain_n.value()
            if n and self.chain_count >= n:
                self.chain_run = False; self._set_phase("done")
                self._say(f"Série terminée : {self.chain_count} essais enchaînés."); return
            gap = self.gap.value()
            self._set_phase("gap")
            self._say(f"Essai {self.chain_count}{'/' + str(n) if n else ''} terminé · suivant dans {gap} ms (Stop pour arrêter).")
            self.gap_timer.start(gap)
            return
        c["t_end"] = time.monotonic()
        self._set_phase("done" if c["answered"] else "answering")
        self._say("Lecture terminée." if c["answered"] else "Choisis la couleur et le chiffre de la phrase cible.")

    def _chain_next(self):
        if self.chain_run:
            self._new_trial()

    def _replay(self):
        if self.cur:
            self.fb.setText("")
            self.chain_run = False
            self._play_current()

    def _stop(self):
        was_chain = self.chain_run or self.cb_chain.isChecked()
        self.chain_run = False
        self.gap_timer.stop()
        self.token += 1
        self.player.stop()
        if not self.cur:
            self._set_phase("idle")
        else:
            self._set_phase("done" if (self.cur["answered"] or was_chain) else "answering")
            if self.phase == "answering":
                self.cur["t_end"] = time.monotonic()
        self._say("Enchaînement arrêté." if was_chain else "Lecture interrompue.")

    def _synth(self):
        self.chain_run = False; self.gap_timer.stop(); self.token += 1
        data = spatial.test_bursts(self.geo.az_t, self.geo.az_m, self.master.value())
        try:
            self.player.play(data, spatial.FS, lambda: None)
        except Exception as e:
            self._say(f"Erreur de lecture audio : {e}"); return
        self._say(f"Test : 3 salves à l'angle de la cible ({self.geo.az_t:g}°), puis 2 salves longues à celui du masqueur ({self.geo.az_m:g}°).")

    def _update_info(self):
        c = self.cur
        if not c:
            self.info.setText(""); return
        if self.cb_hide.isChecked() and not c["answered"]:
            self.info.setText(f"Essai {len(self.log.rows) + 1} · identité des phrases masquée jusqu'à la réponse.")
            return
        d = lambda e: f"{e.label()} · {(e.talker or '?').upper()} ({e.name})"
        self.info.setText(f"Cible : {d(c['te'])} · Masqueur : {d(c['me'])}")

    def _answer(self, color, num):
        c = self.cur
        if self.phase != "answering" or not c:
            return
        rt = round((time.monotonic() - c["t_end"]) * 1000)
        te = c["te"]
        ok = color == te.color and num == te.number
        c["answered"] = True
        self.log.add(len(self.log.rows) + 1, self.pid.text().strip(), te, c["me"], c["az_t"], c["az_m"], c["snr"],
                     (color, num, ok, rt))
        self._set_phase("done"); self._update_info(); self._render_log()
        self.fb.setStyleSheet(f"font-weight:bold;color:{'#1f7a4d' if ok else '#b42318'}")
        self.fb.setText("Correct ✓" if ok else f"Incorrect ✗ — attendu : {te.color} {te.number}")
        self._say("")

    # ---- journal
    def _render_log(self):
        rows = self.log.rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            has = r["correct"] != ""
            vals = [r["trial"], f"{r['target_callsign'].capitalize()} {r['target_color']} {r['target_number']}",
                    f"{r['masker_callsign'].capitalize()} {r['masker_color']} {r['masker_number']}",
                    r["target_talker"].upper(), r["masker_talker"].upper(), f"{r['target_az']}°", f"{r['masker_az']}°",
                    f"{r['separation']}°", r["snr_db"],
                    f"{r['resp_color']} {r['resp_number']}" if has else "—", ("✓" if r["correct"] else "✗") if has else "—",
                    r["rt_ms"] if has else "—"]
            for j, v in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents(); self.table.scrollToBottom()
        by = self.log.by_separation()
        lines = []
        if self.log.n_unanswered():
            lines.append(f"{self.log.n_unanswered()} essai(s) enchaîné(s) sans réponse, non comptés dans les pourcentages.")
        lines += [f"Séparation {k:g}° : {ok}/{n} ({round(100 * ok / n)} %)" for k, (n, ok) in by.items()]
        self.summary.setText("<br>".join(lines))
        self.b_csv.setEnabled(bool(rows)); self.b_clear.setEnabled(bool(rows))

    def _export_csv(self):
        import datetime as dt
        pid = "".join(ch for ch in self.pid.text() if ch.isalnum() or ch in "_-") or "sans-id"
        name = f"VegahSpatial_{pid}_{dt.datetime.now():%Y%m%d-%H%M}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le journal", os.path.join(os.path.expanduser("~"), name), "CSV (*.csv)")
        if path:
            self.log.save_csv(path)
            self._say(f"Journal enregistré : {path}")

    def _clear_log(self):
        if QMessageBox.question(self, "Vider le journal", "Vider le journal des essais ?") == QMessageBox.Yes:
            self.log.clear(); self._render_log()

    def closeEvent(self, ev):
        self.chain_run = False; self.gap_timer.stop(); self.token += 1; self.player.stop()
        if self.log.rows and not self.log.saved:
            r = QMessageBox.question(self, "Journal non exporté", "Le journal n'a pas été exporté en CSV. Quitter quand même ?")
            if r != QMessageBox.Yes:
                ev.ignore(); return
        ev.accept()
