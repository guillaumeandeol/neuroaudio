# Vegah v4 — choix du mode : dépistage ou clinique

Deux pages autonomes : tout (code, corpus, bruits) est embarqué dans chaque fichier HTML.
Aucun dossier `audio/` n'est nécessaire ici.

| Page | URL | Pour qui |
|---|---|---|
| `menu.html` | https://guillaumeandeol.github.io/neuroaudio/v4/menu.html | **Menu** — choisir l'une des entrées ci-dessous |
| `index.html` | https://guillaumeandeol.github.io/neuroaudio/v4/ | Examinateur — choix du mode, configuration complète, vérification du SNR |
| `patient.html` | https://guillaumeandeol.github.io/neuroaudio/v4/patient.html | Sujet — **dépistage** (test court) |
| `patient.html?mode=clinique` | https://guillaumeandeol.github.io/neuroaudio/v4/patient.html?mode=clinique | Sujet — **clinique** (test complet) |
| `dev.html` | https://guillaumeandeol.github.io/neuroaudio/v4/dev.html | Mise au point — **passation simulée**, résultat normal ou anormal en une seconde |

## Ce qui change par rapport à la v3

**Deux modes de passation**, choisis au lancement du test :

- **Dépistage** (inchangé) : test principal à -9 dB, 32 essais. Normal à 19 bonnes réponses ou plus,
  anormal à 6 ou moins ; entre les deux, deux séries de confirmation à -12 puis -6 dB.
- **Clinique** : les trois séries (-9, -12 puis -6 dB, 96 essais, ~15 min) sont **toujours** passées,
  pour estimer le SRT (SNR à 50 % de réussite) quel que soit le score du test principal. La
  classification de la première série est rappelée à côté.

Le sujet ne choisit pas le mode : c'est le lien ouvert qui le fixe, et la page affiche « Test court »
ou « Test complet » sous son titre.

**Estimation du SRT** : régression logistique sur les séries dont le score est strictement entre
0 et 100 %, SRT = −b0/b1, comme dans l'app de normalisation CRM
(<https://ipiup.github.io/CRM_normalization/>). Elle remplace la régression linéaire de la v3, et
s'applique aussi aux confirmations du dépistage. Un SRT hors de l'intervalle testé est signalé
comme extrapolé. La référence est le modèle normatif de cette app (43 sujets normo-entendants,
SRT normatif -11,1 dB) ; l'examinateur voit le **SRT final**, son écart à la norme et s'il dépasse la
marge de 3 dB (limite -8,1 dB), ainsi que la zone rouge / orange / vert de chaque série selon la règle
de l'app (IC de Wilson 95 % comparé à la norme décalée de 3 dB). Le sujet voit le verdict, sans décibels. L'écran de résultats de l'examinateur reprend la section
« Psychometric curve — Eligibility zone » de cette app : même graphique, même tableau de résultats
détaillés, même carte SRT50.

**Côté sujet**, un écran « Courte pause » annonce chaque changement de série (le niveau de bruit
change). En v3, ces séries s'enchaînaient sans prévenir.

**Corrections** : un test interrompu pendant une confirmation n'affiche plus un écran de résultats
vide ; tout test interrompu conclut « Test interrompu » et affiche le reste des résultats.

**Résultats et exports** : l'écran s'arrête à la bande de couleur (plus de tableau essai par essai).
Deux exports : un **classeur Excel** (feuilles *Compte rendu*, *Séries*, *Essais*) et un **PDF** de
compte rendu, avec les coordonnées de l'examinateur s'il les saisit. En cas de résultat anormal, un
encadré « Conduite à tenir » indique qu'un bilan auditif avec audiométrie vocale dans le bruit sur
dispositif médical est nécessaire. Le SRT est donné avec son intervalle de confiance à 95 %, et le
temps de réponse cumulé est affiché par série (délai entre le début de la phrase et le clic).

L'indicatif est **Delta** dans les trois pages.
