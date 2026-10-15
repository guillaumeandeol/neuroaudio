# VegahSpatial — version Python (développeur)

Tâche de compréhension de la parole dans la parole (corpus CRM français) **spatialisée**, un seul masqueur.
Application de bureau (Windows, macOS, Linux) équivalente à la page web `VegahSpatial/dev.html`.

## Installation (une fois)

Il faut Python 3.9 ou plus récent (https://www.python.org).

**Le plus simple** : double-cliquer sur `lancer_vegahspatial.bat` (Windows) ou `lancer_vegahspatial.command` (macOS).
Au premier lancement, le script crée un environnement `.venv` et installe les bibliothèques (quelques minutes, connexion internet nécessaire) ; les lancements suivants sont immédiats.

**À la main** :

```
python -m venv .venv
.venv\Scripts\activate            (macOS / Linux : source .venv/bin/activate)
pip install -r requirements.txt
python -m vegah_spatial
```

Sous Linux, installer aussi PortAudio (`sudo apt install libportaudio2`).

## Utilisation

1. **Casque obligatoire.** Régler d'abord le volume du système bas, puis utiliser « Test de spatialisation (bruits) » pour vérifier que les sons viennent bien de la gauche / de la droite.
2. **Corpus** : l'archive contient 256 phrases d'un locuteur masculin (T0) dans `corpus_demo/`, chargées automatiquement. Pour utiliser le corpus complet : « Choisir le dossier du corpus… » (par ex. `2-Validated-corpus`, fichiers `T5_F_Delta_Rouge_2.wav`) ou `python -m vegah_spatial --corpus DOSSIER`.
3. **Position des sources** : la cible (C) et le masqueur (M) sont toujours à la **même distance** de l'auditeur. En mode symétrique, un curseur règle la distance angulaire (0–180°) de part et d'autre du droit devant (0°) ; on peut aussi glisser les pastilles sur le plan, choisir le côté de la cible, ou passer en mode libre.
4. **Locuteurs** : la cible et le masqueur peuvent avoir la **même voix** (« même que la cible »), des voix différentes, ou un locuteur imposé (nécessite plusieurs locuteurs dans le corpus chargé).
5. **Essai** : « Nouvel essai » joue une phrase cible (indicatif choisi, par défaut Delta) et un masqueur (autre indicatif, autre couleur, autre chiffre). Répondre avec la grille couleur × chiffre. L'option « enchaîner les essais sans attendre de réponse » enchaîne les essais (pause et nombre réglables ; Stop pour arrêter).
6. **Résultats** : journal des essais, pourcentage de réussite par séparation, export CSV (UTF-8, séparateur `;`).

Options de lancement : `--corpus DOSSIER`, `--device N` (carte son ; `--list-devices` pour les lister), `--no-audio` (simulation sans son).

## Méthode

- Spatialisation binaurale par convolution avec les **HRIR KEMAR du MIT** (pavillon normal, plan horizontal, mesures tous les 5°, Gardner & Martin, 1994 ; données réutilisées depuis le paquet `slab`, licence MIT). Les angles intermédiaires sont interpolés après alignement du retard d'attaque (retard interaural d'environ 0,6 ms à 90°).
- **SNR** : niveau RMS de la cible moins celui du masqueur, mesurés sur les signaux d'origine avant spatialisation ; chaque phrase est d'abord ramenée au même RMS de référence (−26 dBFS), puis le niveau général est appliqué. Un limiteur évite l'écrêtage (signalé à l'écran).
- Les HRIR sont **génériques** (tête artificielle) : le rendu varie d'un auditeur à l'autre, et le niveau acoustique n'est pas calibré. Outil de recherche en développement, pas un examen.

## Tests

```
python tests/test_core.py
python tests/test_gui.py        (interface testée hors écran)
```
