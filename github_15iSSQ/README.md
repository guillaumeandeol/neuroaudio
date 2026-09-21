# Questionnaire 15iSSQ

Version électronique du questionnaire d'habiletés auditives **15iSSQ**
(version française abrégée du *Speech, Spatial and Qualities of Hearing scale*).

Application autonome : un seul fichier HTML, aucune dépendance, aucun serveur.
Tout le calcul (scores par partie, comparaison aux normes normo-entendants,
écarts en écarts-types) se fait dans le navigateur.

## Confidentialité

L'application ne transmet **aucune donnée** : rien n'est envoyé ni enregistré
sur un serveur. Les réponses restent dans le navigateur du participant et
disparaissent à la fermeture de la page.

## Mise en ligne sur GitHub Pages

1. Sur https://github.com, cliquez sur **New repository**.
   Nom suggéré : `questionnaire-15issq`. Visibilité : **Public**
   (nécessaire pour que Pages soit gratuit et que le lien s'ouvre sans compte).
2. Envoyez le contenu de ce dossier à la racine du dépôt
   (`index.html` et ce `README.md`) — par glisser-déposer via
   **Add file → Upload files**, ou en ligne de commande (voir plus bas).
3. Dans le dépôt : **Settings → Pages**.
   Sous *Build and deployment*, choisissez **Source : Deploy from a branch**,
   puis **Branch : `main`** et **dossier `/ (root)`**. Cliquez sur **Save**.
4. Attendez une à deux minutes. L'adresse publique s'affiche en haut de cette
   même page, sous la forme :

   `https://<votre-identifiant-github>.github.io/questionnaire-15issq/`

C'est cette adresse à communiquer aux collègues et aux participants.

### En ligne de commande

```bash
cd github_15iSSQ
git init
git add .
git commit -m "Questionnaire 15iSSQ"
git branch -M main
git remote add origin https://github.com/<votre-identifiant>/questionnaire-15issq.git
git push -u origin main
```

Puis effectuez l'étape 3 ci-dessus.

## Mise à jour

Remplacez `index.html` et validez (commit) : le site se republie
automatiquement en une ou deux minutes.

Si une ancienne version s'affiche encore chez un collègue, c'est le cache du
navigateur : Ctrl+Maj+R (Cmd+Maj+R sur Mac) force le rechargement.

## Impression / archivage

Le bouton **Imprimer / PDF** de la page de résultats produit un compte rendu
imprimable ou enregistrable en PDF.
