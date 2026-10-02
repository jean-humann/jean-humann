# Dossier des services et fonctionnalités Hemera v2

Ouvrir [index.html](index.html) pour les fiches de services et chapitres,
[le dossier intégral](../12-dossier-services-fonctionnalites.html) pour la lecture
continue ou [son PDF](exports/hemera-v2-dossier-complet.pdf) pour le partage.
La [matrice](fonctionnalites.html) filtre les capacités par service et texte.
Chaque fiche possède son PDF dans `exports/`.

Les 22 services ont des fiches fonctionnelles. Les 34 composants de support ont
une disposition explicite et un gate de migration. Les déclarations statiques
d’interfaces sont une annexe distincte : préfixes, conditions de montage et
configuration du déploiement empêchent d’en déduire un nombre de routes actives.
La lecture ne certifie pas tous les chemins de code. Les critères d’acceptation
sont proposés ; ils ne sont pas annoncés comme exécutés sur les services.

## Sources et reconstruction

`research/*.json` contient les fiches relues, les observations, propositions et
références fichier/ligne. Les trois lots Kotlin détaillent les six services
existants ; les lots sécurité, applications et IA complètent les 16 autres.
Les chapitres transverses consolident les études déjà produites. Les scripts ne
copient pas le code des dépôts inspectés dans le dossier.

`inventory.py` recense les arbres locaux sans les modifier. `inventory.json`
conserve leurs HEAD et la présence de modifications locales. `validation.json`
ajoute les empreintes des fichiers cités, car HEAD seul ne décrit pas les arbres
Icegres/Eidos modifiés. Les chemins locaux se configurent par options.

```bash
python3 docs/hemera-v2/dossier/inventory.py \
  --monorepo /chemin/cleyrop \
  --icegres /chemin/icegres \
  --eidos /chemin/eidos \
  --reference /chemin/iceberg-data-platform
python3 docs/hemera-v2/dossier/build.py
```

Le générateur utilise la bibliothèque standard Python. CSS, JavaScript et SVG
sont embarqués dans chaque HTML, sans CDN. Le changement de thème et la matrice
fonctionnent hors ligne. Les liens vers les annexes restent relatifs ; conserver
l’arborescence pour naviguer entre les documents.

Pour contrôler les sources, les liens et la couverture après génération :

```bash
python3 docs/hemera-v2/dossier/validate.py \
  --monorepo /chemin/cleyrop \
  --icegres /chemin/icegres \
  --eidos /chemin/eidos \
  --reference /chemin/iceberg-data-platform
```

Les contrôles navigateur et PDF demandent Playwright, Chrome/Chromium et
`pdfinfo`/`pdftotext` dans le PATH. Ajouter `--browser --export-pdf` et, si besoin,
`--chrome /chemin/Chrome` et `--screenshots /tmp/captures-dossier`. L’export crée
28 PDF : intégral, 22 services et cinq chapitres. La vérification teste le filtre
par service, la recherche, les thèmes, la largeur mobile et l’absence de requête
réseau. Elle vérifie aussi que tous les IDs de capacités figurent dans le texte
du PDF intégral.

## Contrat des fiches

Chaque capacité possède un identifiant stable, un comportement observé, des
acteurs, interfaces, données, dépendances, une cible, une migration, une recette
et des références. `capabilities.json` et `fonctionnalites.csv` sont dérivés.
Les noms des domaines Rust sont des responsabilités proposées, pas la liste de
binaires déjà implémentés. Le publisher, le writer de confiance et le service
query ne partagent pas implicitement leurs privilèges.

Le prototype a passé sa démo et ses dix tests avant les modifications de cette
rédaction. Cette validation documentaire n’étend pas la portée du banc réel ni
ne ferme les gates de sécurité, concurrence, reprise et parité décrits dans 10.
