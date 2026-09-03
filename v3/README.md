# Vegah v3 — version avec SNR décroissant en entraînement

Deux pages autonomes : tout (code, corpus, bruits) est embarqué dans chaque fichier HTML.
Aucun dossier `audio/` n'est nécessaire ici — le dossier `audio/` de la racine du dépôt sert la v2.

| Page | URL | Pour qui |
|---|---|---|
| `index.html` | https://guillaumeandeol.github.io/neuroaudio/v3/ | Examinateur — configuration complète et vérification du SNR |
| `patient.html` | https://guillaumeandeol.github.io/neuroaudio/v3/patient.html | Sujet — réglages figés, SNR et score masqués |

## Ce qui change par rapport à la v2 (racine du dépôt)

L'**entraînement** n'est plus une série d'essais au SNR du test : son SNR descend par paliers
réguliers, de +6 dB à -9 dB par pas de 3 dB sur 6 essais par défaut. Le dernier palier est toujours
le SNR du test qui suit, donc l'entraînement débouche exactement sur les conditions du test.
Une jauge de pastilles indique la montée en difficulté sans révéler le SNR au sujet.

Les paliers faciles sont obtenus en **atténuant le bruit**, la voix restant au niveau qu'elle a
pendant le test : le niveau de parole ne bouge pas d'un palier à l'autre, et aucun palier n'écrête
(monter la voix de +15 dB porterait la crête des phrases les plus fortes au-delà du 0 dBFS).
Au SNR du test, le calcul redonne exactement celui de la v2 : **le test principal, les phases de
confirmation et la conclusion clinique sont inchangés.**

Prototype de recherche — pas un dispositif médical calibré.
