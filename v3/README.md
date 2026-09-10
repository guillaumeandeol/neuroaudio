# Vegah v3 — version avec niveau de bruit relatif croissant en entraînement

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

Le sujet est prévenu du déroulement à trois moments : une carte « Déroulement » en deux temps sur
l'écran d'accueil, un bandeau « Entraînement — ne compte pas » pendant l'entraînement, et un écran
d'annonce « La mesure commence » qu'il valide lui-même avant le premier essai comptabilisé.
Cet écran affiche aussi le **bilan de l'entraînement** : score, détail essai par essai, et un message
qui dit si la tâche a été correctement réalisée. Le message est fondé sur la moitié la moins bruitée
de l'échelle — se tromper aux derniers essais est attendu et ne signale rien. Si ce bilan est mauvais,
l'entraînement peut être refait une fois. Cet écran est propre à la page sujet.

L'écran de résultats situe le score sur une **échelle de décision** : zone anormale (6 bonnes réponses
ou moins sur 32), zone intermédiaire, zone normale (19 et plus), avec un repère au score obtenu.
Côté examinateur, la courbe score/SNR montre en plus la limite de décision sur le SNR-50.

Côté sujet, le rapport signal/bruit en décibels n'apparaît nulle part, résultats compris. Le CSV, lui,
contient tout : les essais d'entraînement y figurent avec une colonne `comptabilise` (0) à côté des
essais de la mesure (1).

Les paliers faciles sont obtenus en **atténuant le bruit**, la voix restant au niveau qu'elle a
pendant le test : le niveau de parole ne bouge pas d'un palier à l'autre, et aucun palier n'écrête
(monter la voix de +15 dB porterait la crête des phrases les plus fortes au-delà du 0 dBFS).
Au SNR du test, le calcul redonne exactement celui de la v2 : **le test principal, les phases de
confirmation et la conclusion clinique sont inchangés.**

Prototype de recherche — pas un dispositif médical calibré.
