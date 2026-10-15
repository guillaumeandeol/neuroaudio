"""Lancement : python -m vegah_spatial [--corpus DOSSIER] [--no-audio] [--device N] [--list-devices]"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(prog="vegah_spatial", description="VegahSpatial — CRM spatialisé (version développeur)")
    ap.add_argument("--corpus", help="dossier du corpus CRM (wav/mp3, noms du type T5_F_Delta_Rouge_2.wav)")
    ap.add_argument("--no-audio", action="store_true", help="aucune sortie sonore (simulation des durées)")
    ap.add_argument("--device", type=int, help="numéro de la carte son de sortie (voir --list-devices)")
    ap.add_argument("--list-devices", action="store_true", help="liste les cartes son de sortie et quitte")
    a = ap.parse_args()
    if a.list_devices:
        from .player import SdPlayer
        for i, n in SdPlayer.devices():
            print(i, n)
        return 0
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .gui import MainWindow
    from .player import make_player
    app = QApplication(sys.argv)
    try:
        player = make_player(a.no_audio, a.device)
    except Exception as e:                                  # PortAudio / sounddevice indisponible
        QMessageBox.warning(None, "VegahSpatial", f"Sortie audio indisponible ({e}).\nL'application démarre en mode simulation, sans son.")
        player = make_player(True)
    w = MainWindow(player)
    folder = a.corpus
    if not folder:                                          # corpus de démonstration livré avec l'archive
        demo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus_demo")
        folder = demo if os.path.isdir(demo) else None
    if folder:
        w.load_corpus(folder)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
