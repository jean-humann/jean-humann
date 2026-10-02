# Hemera v2 — série de documents de design

Douze documents principaux et huit planches dédiées, en HTML autoportant,
sans CDN, avec thème clair/sombre. L’[atlas visuel](11-atlas-visuel.html)
est l’entrée pour une lecture mixte direction et équipes techniques.
Les documents 01 à 07 conservent leur version historique publiée. Les addenda
08 à 10 intègrent la demande du 2 octobre 2026 : cores Rust, zéro JVM dans la
cible finale, Icegres/Eidos et les preuves de reprise. En cas de contradiction,
les six invariants du HANDOVER et ces addenda priment sur les anciennes
propositions. La seconde relecture corrige le corps de 08–10 et du DESIGN du
prototype ; le [registre de corrections](11-atlas-visuel.html#relecture)
relie aussi les sept originaux à leur règle actuelle. Les liens sont locaux.

## Lecture

Ouvrir n'importe quel fichier dans un navigateur, ou servir le dossier :

```bash
cd docs/hemera-v2
python3 -m http.server 8000
# puis http://localhost:8000/11-atlas-visuel.html
```

## Ordre de lecture

| # | Fichier | Contenu |
|---|---------|---------|
| ① | `01-architecture-flows-datasets.html` | Architecture : existant, Spark Connect, Lakekeeper+OpenFGA, service Flows, WAP, Catalog & lignage, plan de mise en œuvre |
| ② | `02-modele-de-developpement.html` | Modèle de développement : 9 kinds, contrat d'édition & PEP, SDK `lake`, wraps dbt/SQLMesh/MLflow, quatre étages moteurs EL, proxy Embeddings |
| ③ | `03-design-frontend.html` | Design frontend : 30 écrans en 8 modules, 5 parcours, panneaux sources par classe de flux |
| ④ | `04-annexe-schema-iceberg.html` | Annexe schéma Iceberg : faits F1–F16, règles R1–R14, machine à états des migrations |
| ⑤ | `05-revue-integration.html` | Revue d'intégration : coutures A–G, campagnes I1–I12, décisions D1–D3, checklist E-INT |
| ⑥ | `06-annexe-el-cdc-olake.html` | Annexe EL & CDC : étude OLake (faits E1–E13 + banc S7), design EL v2 exactly-once, Industrie 4.0, grille unifiée des flux, tickets EL-1…EL-13 |
| 🗺️ | `07-planche-olake-classes-flux.html` | Planche visuelle : graphe d'intégration OLake, chronologie exactly-once, classes de flux A/B/C en graphes détaillés, carte des services, panneaux frontend |
| ⑧ | [`08-plateforme-rust-sans-jvm.html`](08-plateforme-rust-sans-jvm.html) | Étude consolidée des 20 missions : comparaison de la référence, services Rust, contrôle/données, Icegres/Eidos, retrait JVM et migration |
| ⑨ | [`09-decision-el4-wap.html`](09-decision-el4-wap.html) | Décision EL-4 : extracteur Go, writer/publisher Rust, WAP et publish-then-ack ; confidentialité et CDC |
| ⑩ | [`10-preuves-et-campagnes.html`](10-preuves-et-campagnes.html) | Préflight vert, campagnes réelles, échecs et limites, quatre contre-épreuves du prototype, registre des 20 missions |
| ⑪ | [`11-atlas-visuel.html`](11-atlas-visuel.html) | Huit planches interactives, lectures Synthèse/Technique, SVG éditables, PDF et registre de relecture |
| ⑫ | [`12-dossier-services-fonctionnalites.html`](12-dossier-services-fonctionnalites.html) | Dossier intégral des 22 services : capacités sourcées, API, états, dépendances, cible Rust, migration et critères de recette ; 34 composants de support, Icegres/Eidos et référence |

Pour reprendre le travail après les lectures obligatoires du HANDOVER, lire 08,
puis 09 et 10 avant d’implémenter le backlog. Les sept documents initiaux donnent
le détail des contrats historiques, pas un état intégralement validé de la cible.

## Planches et exports

| Planche | Sujet |
|---|---|
| [01 — Carte de plateforme](visuels/01-carte-plateforme.html) | Contrôle, données, writer et publisher de confiance |
| [02 — Avant / cible](visuels/02-avant-cible.html) | Retrait de toutes les JVM, contrats conservés, candidats ouverts |
| [03 — Icegres / Eidos](visuels/03-icegres-eidos.html) | Lecture épinglée et action passant par Flows |
| [04 — Publication / ack](visuels/04-edition-publish-ack.html) | Six scénarios interactifs : normal, veto, conflit, réponse perdue, zombie, ack incertain |
| [05 — Sécurité](visuels/05-securite-frontieres.html) | Confidentialité des octets et privilèges de commit |
| [06 — Kinds](visuels/06-kinds-provenance.html) | Huit datasets ; EXPORT comme effet, EXPOSURE comme déclaration |
| [07 — Migration](visuels/07-migration-decisions.html) | Dépendances, cohortes et preuves d’acceptation |
| [08 — Preuves](visuels/08-preuves-risques.html) | Neuf familles de contrats, sans score de maturité |

Chaque planche fournit deux SVG (clair/sombre) et un PDF avec annexe technique.
Les dossiers [direction, trois pages](visuels/exports/hemera-v2-synthese.pdf) et
[complet, seize pages](visuels/exports/hemera-v2-atlas-complet.pdf) sont prêts à
partager. Voir le [guide de reconstruction et validation](visuels/README.md).

## Dossier détaillé des services

Le [portail du dossier](dossier/index.html) donne accès aux 22 fiches de services,
à la [matrice consultable](dossier/fonctionnalites.html), à ses
[exports CSV](dossier/fonctionnalites.csv) et aux cinq chapitres transverses.
Le [PDF intégral](dossier/exports/hemera-v2-dossier-complet.pdf) réunit les
fiches et contrats ; chaque service et chapitre possède aussi son PDF.
Les 744 déclarations statiques d’interfaces ont une annexe séparée et ne sont
pas assimilées à 744 routes actives.

Le [guide de reconstruction](dossier/README.md), le
[registre de couverture](dossier/coverage.json) et le
[rapport de validation](dossier/validation.json) précisent le périmètre.
Les critères de recette décrits restent à exécuter sur la cible.

## Versions en ligne

Les originaux 01 à 07 sont référencés ci-dessous. Ils n’ont pas été modifiés par
ces reprises ; leurs copies locales ont été conservées. Les addenda 08 à 12
sont de nouveaux documents locaux, sans version claude.ai annoncée :

- ① https://claude.ai/code/artifact/0554ae1e-f790-43ba-be76-4a5d48b5d66d
- ② https://claude.ai/code/artifact/bfe50817-4c01-491d-80e3-87fec735ee1e
- ③ https://claude.ai/code/artifact/417e3795-4bb9-44c1-873a-96d462e577c7
- ④ https://claude.ai/code/artifact/3c021de2-d8b1-4f1d-8fb0-da825af2efc3
- ⑤ https://claude.ai/code/artifact/17756242-b7ce-483b-8eee-75a48927a725
- ⑥ https://claude.ai/code/artifact/cfd1ddc0-a4c1-4d37-a1c1-d6a0897b872c
- 🗺️ https://claude.ai/code/artifact/6f82a456-8fc5-41bd-9cfb-23806041d5b0

## Code associé

Le prototype exécutable du framework est dans [`../../cleyrop-dm/`](../../cleyrop-dm/)
(voir son README pour lancer la démo).

## Preuves reproductibles

- [Banc réel Lakekeeper/OpenFGA/Spark Connect](../../cleyrop-dm/experiments/hemera-v2-review/README.md) : scripts, versions épinglées, résultats assainis. Spark et Keycloak servent uniquement de références transitoires.
- [Contre-épreuves locales du prototype](../../cleyrop-dm/experiments/prototype-counteraudit/README.md) : quatre écarts reproduits, distincts des dix tests existants.

Les résultats du banc portent sur des données synthétiques. Les 33 entrées se
recoupent ; leur statut décrit une sonde ou un gate, pas l’acceptation de la
plateforme. La [classification par contrat](visuels/evidence-classification.json)
précise les limites d’I4, I6 et I8. Confidentialité, TTL et parité SQL empêchent
une conclusion globalement verte. La relecture visuelle n’a pas relancé le banc.

## Synchroniser un document publié

Si un document 01 à 07 est modifié sur claude.ai, télécharger son HTML final,
remplacer sa copie locale puis réécrire les URL `claude.ai/code/artifact/<id>`
avec le fichier correspondant dans la table ci-dessus. Préserver les fragments
d’ancres lorsqu’ils existent. Vérifier chaque cible et ancre, l’équilibrage des
balises, les SVG thémés et l’absence de dépendances CDN. Une simple modification
locale n’actualise pas la version en ligne. Ne pas annoncer une synchronisation
sans téléchargement et comparaison du document publié.
