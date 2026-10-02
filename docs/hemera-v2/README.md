# Hemera v2 — série de documents de design

Sept documents HTML autoportants (aucune dépendance réseau, thème clair/sombre
automatique). Les liens croisés entre documents sont locaux : la navigation
fonctionne entièrement hors-ligne.

## Lecture

Ouvrir n'importe quel fichier dans un navigateur, ou servir le dossier :

```bash
cd docs/hemera-v2
python3 -m http.server 8000
# puis http://localhost:8000/01-architecture-flows-datasets.html
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

## Versions en ligne

Les originaux restent publiés sur claude.ai (mêmes contenus) :

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
