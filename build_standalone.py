#!/usr/bin/env python3
"""Génère crm_standalone.html à partir du dossier webapp/.

Le build autonome est un fichier HTML unique, ouvrable par double-clic, sans
serveur ni dossier audio : le CSS, le JS et les fichiers audio (en data: URI)
y sont embarqués. Le code de l'app est celui de webapp/app.js, tel quel — la
seule différence est que audioUrl() y résout les fichiers depuis
window.EMBEDDED_AUDIO au lieu du dossier audio/.

Usage :
    python3 build_standalone.py                      # index.html, indicatif Alpha (32 phrases)
    python3 build_standalone.py --page patient.html --callsigns Delta
    python3 build_standalone.py --callsigns Alpha,Delta
    python3 build_standalone.py --all                # les 8 indicatifs (~7 Mo)
    python3 build_standalone.py --out /tmp/test.html
"""

import argparse, base64, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WEBAPP = os.path.join(ROOT, "webapp")
AUDIO = os.path.join(WEBAPP, "audio")
NOISE_FILES = ["noise/corpus_ssn.mp3", "noise/standard_ssn.mp3"]


def data_uri(rel):
    with open(os.path.join(AUDIO, rel), "rb") as f:
        return "data:audio/mpeg;base64," + base64.b64encode(f.read()).decode("ascii")


def load_manifest():
    src = open(os.path.join(AUDIO, "manifest.js"), encoding="utf-8").read()
    return json.loads(src.split("=", 1)[1].strip().rstrip(";"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--callsigns", default="Alpha",
                    help="indicatifs à embarquer, séparés par des virgules (défaut : Alpha)")
    ap.add_argument("--all", action="store_true", help="embarquer tous les indicatifs du manifeste")
    ap.add_argument("--page", default="index.html",
                    help="page de webapp/ à empaqueter (index.html ou patient.html)")
    ap.add_argument("--out", default=None,
                    help="fichier de sortie (par défaut : crm_standalone.html / crm_patient_standalone.html)")
    args = ap.parse_args()

    if args.out is None:
        stem = os.path.splitext(os.path.basename(args.page))[0]
        name = "crm_standalone.html" if stem == "index" else f"crm_{stem}_standalone.html"
        args.out = os.path.join(ROOT, name)

    manifest = load_manifest()
    if args.all:
        callsigns = sorted({e["callsign"] for e in manifest})
    else:
        callsigns = [c.strip() for c in args.callsigns.split(",") if c.strip()]

    entries = [e for e in manifest if e["callsign"] in callsigns]
    if not entries:
        sys.exit(f"Aucune phrase pour les indicatifs {callsigns} dans le manifeste.")

    embedded = {rel: data_uri(rel) for rel in NOISE_FILES}
    for e in entries:
        embedded[e["file"]] = data_uri(e["file"])

    css = open(os.path.join(WEBAPP, "style.css"), encoding="utf-8").read()
    app = open(os.path.join(WEBAPP, "app.js"), encoding="utf-8").read()
    html = open(os.path.join(WEBAPP, args.page), encoding="utf-8").read()

    # CSS en ligne
    html = re.sub(r'<link rel="stylesheet" href="style\.css">',
                  "<style>\n" + css + "\n</style>", html, count=1)

    # liste d'indicatifs restreinte à ce qui est réellement embarqué.
    # Si la page fige déjà un seul indicatif (page patient), on ne touche à rien
    # mais on vérifie qu'il fait bien partie des phrases embarquées.
    sel = re.search(r'<select id="targetCallsign">(.*?)</select>', html, flags=re.S)
    if sel:
        existing = re.findall(r"<option[^>]*>([^<]+)</option>", sel.group(1))
        if len(existing) == 1:
            fixed = existing[0].strip()
            if fixed not in callsigns:
                sys.exit(f"{args.page} fige l'indicatif {fixed}, absent des indicatifs "
                         f"embarqués ({', '.join(callsigns)}) — relancez avec --callsigns {fixed}.")
        else:
            options = "\n".join(f'          <option>{c}</option>' for c in callsigns)
            html = html[:sel.start()] + '<select id="targetCallsign">\n' + options \
                   + '\n        </select>' + html[sel.end():]

    # titre + mention du build
    title = re.search(r"<title>(.*?)</title>", html, flags=re.S)
    base = title.group(1).strip() if title else "Vegah"
    html = re.sub(r"<title>.*?</title>",
                  f"<title>{base} — version autonome ({len(entries)} phrases)</title>",
                  html, count=1, flags=re.S)
    html = html.replace(
        '<p class="disclaimer">',
        '<p class="disclaimer">Version autonome : ' + str(len(entries)) + ' phrases (indicatif '
        + ", ".join(callsigns) + ') et les deux bruits sont embarqués dans ce fichier — aucun '
        'dossier audio ni serveur nécessaire. Générée par build_standalone.py depuis webapp/.<br>', 1)

    prelude = ("window.EMBEDDED_AUDIO = " + json.dumps(embedded) + ";\n"
               "window.CRM_MANIFEST = " + json.dumps(entries, ensure_ascii=False) + ";\n")

    html = html.replace('<script src="audio/manifest.js"></script>',
                        "<script>\n" + prelude + "</script>", 1)
    html = html.replace('<script src="app.js"></script>',
                        "<script>\n" + app + "\n</script>", 1)

    if "EMBEDDED_AUDIO" not in html or "audioUrl" not in html:
        sys.exit("Échec de l'inlining : vérifier les balises <script> de webapp/index.html.")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{args.out} — depuis {args.page}, {len(entries)} phrases "
          f"({', '.join(callsigns)}), {os.path.getsize(args.out) / 1e6:.2f} Mo")


if __name__ == "__main__":
    main()
