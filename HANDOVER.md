# HANDOVER — Hemera v2 / cleyrop-dm

Document de passation pour l'agent (ou la personne) qui reprend ce travail.
Dernière mise à jour : 2026-10-02.

## 1. Le contexte en trois phrases

Ce dépôt porte le travail de design **Hemera v2**, la refonte de la plateforme
data souveraine de Cleyrop : un lakehouse Iceberg gouverné (Lakekeeper +
OpenFGA), un service **Flows** qui orchestre des datasets déclarés par
manifeste, et un modèle où **l'édition publiée** (snapshot Iceberg estampillé)
est l'unique source de vérité — y compris pour les curseurs d'ingestion
(exactly-once par construction). Le design est consigné dans **7 documents HTML**
(`docs/hemera-v2/`) et un **prototype exécutable** (`cleyrop-dm/`) valide les
mécanismes cœur (branches = environnements, WAP, fingerprints, time travel).

## 2. État des lieux — ce qui est FAIT

| Livrable | Où | État |
|---|---|---|
| Série de design (7 docs HTML, FR, autoportants, liens croisés locaux) | `docs/hemera-v2/` | ✅ complet, poussé |
| Prototype framework (`cleyrop_dm`) : DAG SQL/Python, moteurs DuckDB/PyIceberg, WAP, branches, fingerprints, CLI | `cleyrop-dm/` | ✅ démo + 10 tests verts |
| Étude OLake (code lu commit `8dcefff` + banc réel PG16 : backfill CTID, CDC pgoutput borné, 4 events c/c/u/d vérifiés) | doc ⑥, faits E1–E13 + banc S7 | ✅ |
| Design EL v2 (3 classes de flux, quadruplet plage/dédup/ack/watermark, Industrie 4.0) | doc ⑥ §4–5, planche 🗺️ §4 | ✅ |
| Versions publiées en ligne (mêmes contenus que `docs/hemera-v2/`) | liens dans `docs/hemera-v2/README.md` | ✅ |

**Vérifier que tout marche** (5 min) :

```bash
cd cleyrop-dm
python -m pip install -e . pyarrow pytest
python demo.py            # cycle complet : prod → dev zéro-copie → promotion → veto d'audit → time travel
python -m pytest -q       # 10 tests ; utiliser `python -m pytest`, pas `pytest` (PATH ≠ interpréteur pip)
```

## 3. Les invariants du design — à ne PAS casser

1. **La destination est la vérité.** Curseurs, state, provenance vivent dans les
   snapshot properties de la dernière **édition publiée** (`origin.cursor`),
   jamais dans un state file ou le Postgres de Flows (simple cache).
2. **Publish-then-ack.** Une source (slot WAL, consumer group, file) n'est
   acquittée qu'APRÈS la publication de l'édition qui la couvre. Les deux seuls
   crashs possibles convergent (WAP ⇒ rien n'existe avant publish ; recovery
   borné + dédup après).
3. **WAP partout.** Écriture sur branche staging → audits → fast-forward.
   Un veto ⇒ rien n'existe.
4. **Pas de gouvernance sans journal rejouable.** Flux de classe B (MQTT,
   webhooks…) passent par un étage durable d'abord (voir grille doc ⑥ §5).
5. **Les outils tiers sont wrappés, jamais le centre.** OLake/dbt/SQLMesh/dlt
   travaillent à l'intérieur de la frontière : entrées gouvernées, écritures sur
   staging, publication par le flow. Changer d'étage moteur = un placement,
   pas une API différente.
6. **Runs bornés, workers fongibles.** Pas de démon par source ; le pool
   `el`/`el-cdc` prend n'importe quel job car l'état est dans l'édition.

## 4. Carte des documents (ordre de lecture)

`docs/hemera-v2/README.md` donne le détail. En bref : ① architecture →
② modèle de développement (9 kinds, SDK `lake`, PEP) → ③ frontend (30 écrans)
→ ④ annexe Iceberg (F1–F16, R1–R14) → ⑤ revue d'intégration (coutures A–G,
campagnes I1–I12, décisions D1–D3) → ⑥ annexe EL/CDC (E1–E13, banc S7, grille
des flux, Industrie 4.0) → 🗺️ planche visuelle (graphes d'intégration et
classes A/B/C).

## 5. Backlog — par où continuer

Priorité suggérée :

1. **EL-4 (doc ⑥)** — trancher la frontière WAP du writer OLake : écriture sur
   branche via Lakekeeper REST dans le sidecar Java, repli « régime STREAM »
   sinon. C'est la seule décision structurante encore ouverte du design EL.
2. **Campagnes I1–I12 (doc ⑤)** — dérouler la checklist E-INT sur un
   environnement réel (Lakekeeper + OpenFGA + Spark Connect) ; statuts au
   02/07/2026 dans le doc.
3. **Tickets EL-1…EL-13 (doc ⑥ §7)** — implémentation EL v2 : chunks de
   backfill en jobs (EL-2/3), curseur relu de l'édition (EL-2), fenêtre de
   dédup i/c (EL-5), lag de slot en S8 (EL-6), connecteurs IoT (EL-9…12),
   réceptacle webhooks (EL-13).
4. **Prototype** — rapprocher `cleyrop_dm` du design : kinds manquants
   (STREAM, FILESET, EMBEDDINGS), manifeste `source()`, éditions estampillées
   `origin.*`.

## 6. Conventions de travail

- **Branche de développement : `claude/cleyrop-dataset-management-6lftkw`** —
  tout commit/push va là ; ne pas créer de PR sans demande explicite.
- Documents de design : **français**, HTML autoportant (zéro CDN), palette
  Catppuccin via variables CSS `:root` + variante sombre
  (`prefers-color-scheme`), diagrammes SVG inline thémés (`style="...var(--x)"`).
  En cas d'édition : valider l'équilibrage des balises et l'absence de liens
  `claude.ai/code/artifact/...` résiduels dans les copies locales (les liens
  croisés doivent rester relatifs).
- Les versions publiées sur claude.ai et les copies `docs/hemera-v2/` doivent
  rester synchrones : après édition d'un document publié, re-télécharger le
  HTML et refaire la réécriture des liens (voir `docs/hemera-v2/README.md`).
- Code : suivre le style existant de `cleyrop_dm` ; tests via
  `python -m pytest -q`.

## 7. Prompt de reprise (à donner au prochain agent)

> Tu reprends le projet Hemera v2 dans le dépôt `jean-humann/jean-humann`,
> branche `claude/cleyrop-dataset-management-6lftkw`. Lis d'abord `HANDOVER.md`
> à la racine, puis `docs/hemera-v2/README.md` (ordre de lecture de la série)
> et `cleyrop-dm/DESIGN.md`. Vérifie l'environnement : `cd cleyrop-dm &&
> python -m pip install -e . pyarrow pytest && python demo.py && python -m
> pytest -q` (10 tests verts attendus). Respecte les six invariants du §3 du
> HANDOVER. Continue par le backlog §5 dans l'ordre, en committant sur la même
> branche, sans créer de PR sauf demande.
