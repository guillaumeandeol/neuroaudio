# Vegah — CRM audiométrie vocale dans le bruit (prototype web)

Prototype de test d'intelligibilité de la parole dans le bruit basé sur le corpus **CRM français**
(Isnard, Chastres & Andéol, 2024, *JASA Express Letters* 4, 075203).

## Contenu

- `index.html`, `style.css`, `app.js` — l'application (aucune dépendance externe).
- `audio/manifest.js` — description des 256 phrases utilisées (locuteur T0, indicatif, couleur, chiffre),
  exposée en variable JS globale (`window.CRM_MANIFEST`) plutôt qu'en JSON chargé par `fetch`.
- `audio/T0` — les 256 enregistrements du locuteur T0 (homme), convertis en `.mp3`.
- `audio/noise/corpus_ssn.mp3` — bruit continu calé sur le spectre moyen du corpus complet.
- `audio/noise/standard_ssn.mp3` — bruit "speech-shaped" standard (approximation du spectre long terme de la
  parole — LTASS : plat jusqu'à 500 Hz, puis roll-off ~9 dB/octave), indépendant de ce corpus précis.
  Choix entre les deux à l'écran de configuration.

Le format audio est **MP3** (et non Ogg Vorbis) : Safari/WebKit ne décode pas l'Ogg Vorbis via l'API Web
Audio, ce qui empêchait le son de jouer sur Mac/iPhone. Le MP3 est lu nativement partout.

Le corpus complet (8 locuteurs, 2048 phrases) avait été intégré dans une version précédente ; l'app est
maintenant volontairement restreinte au locuteur T0 (voix unique). Des fichiers `.ogg` inutilisés (ancienne
version) et les dossiers `audio/T1` à `audio/T7` peuvent encore traîner sur disque mais ne sont plus
référencés ni utilisés par l'app — ils peuvent être supprimés sans impact si besoin d'alléger le dossier.

## Lancer le prototype

Double-cliquer sur `index.html` suffit — aucun serveur local n'est nécessaire. L'app charge le corpus via
un `<script>` (`audio/manifest.js`) et joue les fichiers via des balises `<audio>`, ce qui fonctionne
directement en `file://`, y compris sur Safari.

Si vous préférez tout de même servir le dossier via HTTP (par ex. pour tester dans des conditions proches
d'un déploiement web), c'est aussi possible :

```bash
python3 -m http.server 8000
```

puis ouvrir `http://localhost:8000`.

## Principe du test

1. **Configuration** : indicatif d'appel cible (le participant répond toujours à la couleur/chiffre qui suit
   cet indicatif), choix du bruit de masquage (corpus ou standard), nombre d'essais (32 par défaut) et
   essais d'entraînement.
2. **Test principal** : à chaque essai, une phrase cible (locuteur T0) est jouée mélangée au bruit continu, à
   un SNR fixe de **-9 dB**. Le participant répond via la grille couleur (Bleu/Jaune/Rouge/Vert) × chiffre
   (1–8). La phrase suivante est présentée automatiquement 1 seconde après chaque réponse (seul le tout
   premier essai nécessite un clic, pour débloquer l'audio).
3. **Conclusion clinique** (calculée uniquement si le test principal comporte exactement 32 essais) :
   - **≥ 19 bonnes réponses sur 32** → normal, test terminé.
   - **≤ 6 bonnes réponses sur 32** → anormal, test terminé.
   - **entre 7 et 18** → ambigu : deux essais de confirmation sont automatiquement enchaînés, un à SNR
     -12 dB et un à SNR -6 dB (même nombre d'essais que le test principal). Les trois pourcentages de bonnes
     réponses (-12, -9, -6 dB) servent à estimer par régression linéaire le SNR donnant 50 % de réussite.
     Si ce SNR estimé est **≥ -8,1 dB**, le sujet est classé anormal (confirmé), sinon normal (confirmé).
4. **Résultats** : conclusion, tableau/graphique des scores par phase de test, export CSV essai par essai
   (avec la phase, le SNR, le locuteur, la cible, la réponse, l'exactitude et le temps de réponse).

## Vérification du SNR

L'écran de configuration contient une carte **« Vérification du SNR »** qui permet de contrôler que le
rapport signal/bruit réellement produit correspond bien au SNR demandé.

- **Bruit seul / Voix seule / Mélange** : les trois boutons jouent les sources aux niveaux exacts appliqués
  pendant le test (bruit à son gain de référence, voix au gain calculé par la même formule que `trialGain()`).
  Le bruit seul est joué exactement la durée de la phrase tirée, pour que la fenêtre de mesure soit identique.
- **Mesure à la lecture** : un tap de mesure est branché juste après le gain de chaque source, donc sur le
  signal réellement envoyé à la sortie. L'app affiche le RMS du bruit, le RMS de la voix (phrase entière et
  parties actives seulement), le SNR mesuré, l'écart au SNR cible et la crête (détection d'écrêtage).
  Les deux mesures se conservent d'une écoute à l'autre : écouter le bruit seul puis la voix seule suffit à
  obtenir le SNR, sans jamais les mélanger.
- **Analyse hors-ligne** : décode les fichiers (`fetch` + `decodeAudioData`) et compare leur RMS exact aux
  constantes `TARGET_RMS_REF` / `NOISE_RMS_REF` sur lesquelles repose tout le calcul de SNR ; affiche
  l'erreur apportée par chaque constante et le SNR réellement produit. Peut aussi analyser N phrases du
  corpus pour montrer la dispersion des niveaux (l'erreur résiduelle liée à l'usage d'une constante unique).
  Cette analyse nécessite un serveur HTTP local (`python3 -m http.server 8000`) : `fetch` est bloqué en
  `file://`. La mesure à la lecture, elle, fonctionne dans les deux cas.

Contrôle effectué hors app sur les fichiers du dossier (ffmpeg + numpy, 256 phrases T0) :
`corpus_ssn.mp3` RMS = 2998,3 (constante 2999,6 → erreur +0,004 dB), `standard_ssn.mp3` RMS = 2998,8,
phrases T0 RMS moyen = 2186,1 (constante 2185,6 → +0,002 dB), étendue 2181,7–2193,1 soit ±0,02 dB.
**Le SNR nominal est donc exact à mieux que ±0,03 dB près sur tout le corpus.**
À noter : ce SNR est défini sur le RMS de la phrase entière (silences compris), conformément à la
normalisation du corpus ; pendant la parole active le rapport est environ **0,7 dB plus favorable**.

## Présentation du bruit : continue ou déclenchée

Deux modes, réglables sur l'écran de configuration (`index.html`) et figés à **déclenché** sur la page
patient. Le SNR est rigoureusement identique dans les deux cas — seule la fenêtre temporelle du bruit change.

- **Déclenché** (défaut) : le bruit démarre `NOISE_LEAD_MS` (500 ms) avant la phrase, s'arrête
  `NOISE_TAIL_MS` (500 ms) après, puis `INTER_TRIAL_MS` (1500 ms) de silence avant l'essai suivant.
  Entrée et sortie en fondu de `NOISE_RAMP_MS` (30 ms) pour éviter les clics. L'extrait de bruit est tiré
  à un endroit aléatoire du fichier à chaque essai.
- **Continu** : le bruit tourne d'un bout à l'autre de la phase, comme dans la version initiale.

Chronologie vérifiée en navigateur (enveloppe du gain de bruit échantillonnée toutes les 10 ms) :
bruit → voix 490–500 ms, fin de voix → coupure du bruit 520 ms, silence inter-essais 1530–1570 ms.
La réécoute rouvre la même fenêtre (500 + durée de la phrase + 500).

### Le bruit qui « s'arrête »

Trois changements structurels enlèvent les causes plausibles du bruit qui s'interrompt en cours de test :

1. Le bruit est **décodé une fois en AudioBuffer** et bouclé par un `AudioBufferSourceNode`, qui boucle
   sans trou par construction. La boucle d'un `<audio loop>` peut, elle, laisser un blanc à chaque tour
   selon le navigateur (padding MP3 non retiré — comportement connu sur WebKit). Repli automatique sur
   l'élément média si le décodage est impossible (page dossier ouverte en `file://`, où `fetch` est bloqué).
2. En mode déclenché, la lecture ne dure que ~3 s prise à un offset au plus égal à `durée - 10 s` :
   **le point de bouclage n'est jamais atteint**, y compris avec le repli élément média.
3. Les éléments média des phrases sont **explicitement libérés** à la fin de chaque essai
   (`removeAttribute("src")` + `load()`). Un test de 32 essais en créait autant sans les relâcher, or le
   nombre d'éléments média simultanés est plafonné sur WebKit/iOS — de quoi faire tomber tout le graphe
   audio, bruit compris, au milieu d'une passation.

Mesure faite au passage : 35 s de bruit bouclé via `<audio loop>` dans Chromium, échantillonné toutes les
23 ms, ne montrent **aucun** blanc au point de bouclage. La cause reste donc à confirmer côté Safari.

Chaque ligne du CSV porte désormais `noiseType` et `noisePresentation`, pour que l'export dise dans
quelles conditions il a été produit.

## Page patient (patient.html)

`patient.html` est la version destinée au sujet : aucun accès au paramétrage. Elle réutilise
**exactement le même `app.js`** que `index.html` — même déroulé d'essais, même calcul de SNR, même
écran de résultats — mais son écran d'accueil ne contient que les consignes, un bouton de réglage du
volume et un bouton « Commencer ».

Réglages figés (bloc `<div hidden id="fixedConfig">` en haut du fichier, seul endroit à modifier) :

| Paramètre | Valeur |
|---|---|
| Indicatif cible | Delta |
| Bruit de masquage | standard (speech-shaped, indépendant du corpus) |
| SNR | -9 dB |
| Essais | 32 |
| Entraînement | 4 |

- **Identifiant participant** : champ visible en haut de l'écran d'accueil (initiales ou numéro), saisi
  par le sujet lui-même. Obligatoire : `startSession()` refuse de démarrer tant qu'il est vide et affiche
  un message sous le champ. Le paramètre d'URL `patient.html?id=P01` reste accepté et prérenseigne le
  champ quand c'est l'examinateur qui lance le test.
  Le caractère obligatoire tient au seul attribut natif `required` sur le champ : l'enlever le rend
  facultatif, sans toucher au JavaScript (c'est pourquoi `index.html`, qui ne le porte pas, démarre
  toujours sans identifiant).
- **Nettoyage de l'identifiant** : `sanitizeParticipantId()` ne conserve que lettres, chiffres, espaces,
  `-` et `_`, limité à 20 caractères — l'identifiant part à la fois dans le nom du fichier CSV et dans
  une colonne du CSV, une virgule ou un `/` y casserait tout. L'identifiant figure désormais dans la
  colonne `participant` de chaque ligne exportée, et plus seulement dans le nom du fichier.
- **Message de vigilance** : un bandeau en tête de l'écran d'accueil prévient le sujet qu'il s'agit d'une
  version en cours de développement, que ce n'est pas un examen médical et que les résultats ne
  constituent ni un diagnostic ni une évaluation de son audition ; il l'invite à consulter en cas de gêne
  auditive. Un rappel plus court est répété en tête de l'écran de résultats, juste au-dessus de la
  conclusion — c'est là que le risque de mésinterprétation est le plus grand, puisque le sujet y voit
  une mention « normal » ou « anormal ». Classe CSS `.vigilance`.
- **Acquittement obligatoire** : une case à cocher (`#ackDev`) au bas du bandeau doit être validée avant
  que le test ne démarre. Elle est branchée via `addStartGuard()` dans `app.js` — une page enregistre une
  fonction qui renvoie `false` pour refuser le lancement et affiche son propre message ; `index.html`
  n'en enregistre aucune et démarre donc sans condition. Si l'identifiant et la case manquent tous les
  deux, les deux messages s'affichent et le focus va au premier bloc en défaut.
- **Nouvelle passation** : « Nouveau test » remet l'identifiant à vide et décoche la case, pour que le
  sujet suivant ne parte pas avec l'identifiant et l'acquittement du précédent.
- **Paramètres masqués pendant le test** : l'attribut `data-hide-parameters` sur `<body>` retire au sujet
  le SNR (`#snrLabel`, et la mention « (SNR -9 dB) » du libellé de phase) et son score en cours
  (`#liveScore`). Le compteur d'essais reste, lui, affiché — c'est un repère de progression, pas un
  paramètre. `index.html` ne porte pas l'attribut et continue de tout afficher.
- **Pas de réécoute** : le bouton `#btnReplay` est absent du DOM de la page patient — chaque phrase est
  entendue une seule fois. Les appels d'`app.js` passent par `setDisplay()`, qui ignore les éléments
  absents. (Le bouton n'apparaissait de toute façon jamais pendant l'entraînement, seulement pendant le
  test comptabilisé.)
- **Fin de test** : le sujet voit l'écran de résultats complet (conclusion clinique, scores, export CSV).
- **Interruption** : le lien discret en bas de l'écran de test demande confirmation avant d'arrêter.
  Son id est `btnStopPatient` (et non `btnStop`) pour que `app.js` ne le câble pas directement.
- Version autonome : `python3 build_standalone.py --page patient.html --callsigns Delta`
  → `../crm_patient_standalone.html`. Le script refuse de construire si l'indicatif figé dans la page
  ne fait pas partie des phrases embarquées.

Le câblage des boutons dans `app.js` passe par `on(sel, ev, fn)`, qui ignore silencieusement les
éléments absents — c'est ce qui permet aux deux pages de partager le même script.

## Build autonome (crm_standalone.html)

`../build_standalone.py` régénère `../crm_standalone.html` à partir de ce dossier : un fichier HTML unique,
ouvrable par double-clic, sans dossier audio ni serveur. Le CSS, le JS (`app.js` tel quel) et les fichiers
audio (en data: URI) y sont embarqués — le build a donc exactement les mêmes fonctionnalités que l'app
dossier, vérification du SNR comprise, y compris l'analyse hors-ligne (les data: URI sont décodées via
`atob`, sans `fetch`).

```bash
python3 build_standalone.py                       # indicatif Alpha, 32 phrases (~1,5 Mo)
python3 build_standalone.py --callsigns Alpha,Delta
python3 build_standalone.py --all                 # les 8 indicatifs (~7 Mo)
```

Le seul point d'adaptation dans `app.js` est `audioUrl(rel)` : elle renvoie `audio/<rel>` normalement, et la
data: URI correspondante quand `window.EMBEDDED_AUDIO` est présent (build autonome). Toute nouvelle lecture
audio doit passer par cette fonction, sinon elle cassera le build autonome.

**Relancer ce script après toute modification de `webapp/`** — sinon `crm_standalone.html` se désynchronise
silencieusement.

## Affichage sur téléphone

La grille de réponse fait 8 colonnes × 4 couleurs, ce qui est le point serré sur un écran de téléphone.
Trois causes de débordement horizontal ont été corrigées (mesuré : `document.scrollWidth` égal à
`clientWidth` de 320 px à 1280 px, sur les trois écrans) :

- `grid-template-columns: repeat(8, minmax(0, 1fr))` et non `1fr`. Avec `1fr`, la largeur *minimale du
  contenu* des boutons impose sa loi : la règle `button` globale leur donnait un `padding: 13px 20px`,
  soit une grille de 425 px sur un écran de 393 px et une 8ᵉ colonne hors champ. `.grid-btn` remet donc
  aussi `padding: 0` et `min-width: 0`.
- `#resultsChart` avait un `width="600"` en dur : `max-width: 100%` le contraint désormais.
- Le tableau d'essais (16 colonnes, ~800 px) est enveloppé dans `.table-scroll` : il défile
  horizontalement dans son propre cadre au lieu d'élargir la page entière.

En dessous de 560 px, la grille déborde de 6 px de chaque côté du padding de la page pour gagner en
surface tactile (les cartes gardent leurs marges). Le seuil est volontairement large : à 420 px, un
iPhone Pro Max (430 px de large) se retrouvait avec des boutons *plus petits* qu'un iPhone 15 Pro.
Boutons obtenus : 34 px à 320 px, 43 px à 393 px, 48 px à 430 px, 79 px sur tablette et bureau.

## Limites du prototype (à garder en tête pour la suite)

- Les niveaux de SNR sont **relatifs** : rien ne calibre le volume de sortie en dB SPL absolus. Pour un usage
  clinique réel, il faudra une étape de calibration matérielle (casque + niveau de référence mesuré).
- Le bruit est un bruit "shaped noise" généré à partir du spectre moyen du corpus, pas un bruit de babble
  multi-locuteurs ni le protocole exact "speech-on-speech" de l'article (ça, c'était le choix "parole dans le
  bruit" plutôt que "parole dans la parole" — facile à ajouter ensuite si besoin, le corpus et le mélangeur audio
  le permettent déjà).
- Pas encore de gestion multi-participants / stockage serveur : tout reste local au navigateur (CSV téléchargé
  en fin de session).
- Le cas "SNR à 50 % < -8,1 dB" est traduit par "normal (confirmé)" par déduction logique (seule alternative
  cohérente à "anormal confirmé" dans l'arbre de décision) — ce n'était pas explicitement précisé, à valider.
- La régression pour estimer le SNR à 50 % est une simple droite des moindres carrés sur 3 points ; robuste
  seulement si les trois scores sont à peu près monotones avec le SNR (sinon le résultat est peu fiable, et
  l'app l'affiche comme "indéterminé" si la droite est parfaitement plate).

## Prochaines étapes suggérées (vers l'app iOS/Android)

- Étape logique suivante : emballer ce web app en PWA (installable, fonctionnement hors-ligne) avant d'envisager
  du React Native / Swift natif, si le protocole de test est validé tel quel.
- Ajouter une calibration de niveau et/ou un mode "speech-on-speech" (TMR) fidèle au protocole exact de l'article.
