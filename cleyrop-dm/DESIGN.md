# Pourquoi le prototype cleyrop-dm existe

`cleyrop-dm` explore une gestion déclarative des datasets Iceberg : modèles
SQL/Python, dépendances, plans, branches, audits et lecture historique. Il
permet de discuter ces mécanismes avec du code exécutable. La frontière de
publication gouvernée de Hemera v2 reste à construire.

Le 2 octobre 2026, la démo complète et les dix tests existants passent.
Quatre contre-épreuves reproduisent pourtant une visibilité avant le premier
audit, une promotion divergente, un audit renforcé ignoré par le plan et
l’exécution de code Python pendant la préparation d’un plan. La présente
révision corrige leur description ; elle ne modifie pas le prototype.

Pour une lecture direction et technique, commencer par l’[atlas
visuel](../docs/hemera-v2/11-atlas-visuel.html), puis la [cible Rust sans
JVM](../docs/hemera-v2/08-plateforme-rust-sans-jvm.html). Les [preuves et leurs
limites](../docs/hemera-v2/10-preuves-et-campagnes.html) distinguent résultats
locaux, campagnes réelles et critères encore ouverts.

## 1. Le problème à résoudre

Un format de table commun ne suffit pas à gouverner les usages. Il faut savoir
quelle définition a produit les données, quelles éditions ont été lues,
quels audits ont autorisé la publication et quelle position source est
effectivement couverte. Il faut aussi reprendre une exécution sans publier
deux fois ni acquitter une plage perdue.

Hemera v2 retient une édition publiée comme autorité des données. Pour une
table, elle référence un snapshot Iceberg identifié. Pour un fichier, un
modèle ou une définition sémantique, elle porte un index ou manifeste Iceberg
qui référence des objets immuables. Les index de recherche, caches et
projections métier doivent pouvoir être reconstruits à partir de ces éditions.

La cible confirmée impose des cœurs métier Rust et zéro JVM, y compris dans
les moteurs, l’identité, les notebooks et les outils d’exploitation finaux.
Le prototype Python reste une référence fonctionnelle. Spark Connect est un
outil temporaire de comparaison ; sa JVM distante ne satisfait pas cette cible.

## 2. Ce que nous reprenons de dbt et SQLMesh

dbt apporte les modèles déclaratifs, les dépendances explicites et les tests.
SQLMesh apporte notamment fingerprints, plans, audits bloquants et
environnements virtuels. Ces idées inspirent le prototype sans imposer que
l’un de ces outils possède la publication ou le curseur d’ingestion.

| Besoin | Apport des outils | Choix Hemera |
|---|---|---|
| Décrire un traitement | SQL, configuration, dépendances et modèles Python selon outil | Manifeste versionné commun au code et à l’interface |
| Sélectionner le travail | dbt possède sélection par état et defer ; SQLMesh exploite ses fingerprints et plans | Distinguer changement logique, nouvelles entrées et revalidation d’audit |
| Réutiliser un environnement | Vues virtuelles, defer ou clone selon moteur | Réutiliser des éditions explicitement épinglées |
| Contrôler une publication | Tests et audits, avec mécanismes propres à l’outil | Audits du candidat exact avant la décision de publication |
| Reprendre une ingestion | États et artefacts propres à chaque exécutant | Curseur et état de reprise portés par la dernière édition publiée |

La sélection par état et defer peuvent limiter le travail exécuté par dbt.
Ses documentations décrivent
[state et defer](https://docs.getdbt.com/reference/node-selection/defer), ainsi
que [clone](https://docs.getdbt.com/reference/commands/clone), dont le mécanisme
dépend de la plateforme. Ces fonctions ne prouvent pas pour autant le contrat
de publication Hemera. Les wrappers dbt, SQLMesh et dlt restent à qualifier
dans un espace privé, avec entrées gouvernées et sorties préparées.

## 3. Ce que le code exécute aujourd’hui

Le runner charge les modèles, construit le graphe et compare leurs fingerprints
avec ceux de SQLite. Pour les modèles sélectionnés, il lit les relations en
Arrow, appelle le moteur ou la fonction Python, matérialise le résultat,
exécute les audits puis enregistre le résultat dans le state store.

| Module | Responsabilité observée |
|---|---|
| `config.py`, `model.py` | Configuration YAML, en-têtes SQL, modèles Python et dépendances |
| `dag.py`, `fingerprint.py`, `plan.py` | Ordre des modèles, hash récursif et sélection des changements |
| `engines/` | Exécution SQL DuckDB et adaptateur Spark Connect |
| `catalog.py` | Tables, branches d’environnement, matérialisation, promotion et scans historiques |
| `audits.py` | Assertions sur les données Arrow calculées |
| `state.py`, `runner.py`, `cli.py` | État local, exécution du plan et commandes utilisateur |

Un modèle SQL décrit par exemple sa sortie et ses audits dans un en-tête :

```sql
-- @model: customer_totals
-- @materialization: table
-- @audits: not_null(customer_id), unique(customer_id)
SELECT customer_id, SUM(amount) AS total_amount
FROM orders
GROUP BY customer_id
```

Les modèles Python exposent `META` et une fonction `model(ctx)`. Le contexte
résout les relations amont en Arrow. Leur chargement exécute actuellement le
module pour lire ses métadonnées. Demander un plan n’est donc pas une opération
sans effets de bord pour un projet Python non maîtrisé.

Trois matérialisations existent : `TABLE`, `INCREMENTAL` et `VIEW`. Une table
existante est remplacée par overwrite ; l’incrémental utilise upsert avec les
clés déclarées. La VIEW est une expression éphémère du graphe, sans édition
persistée propre. Le `source()` d’ingestion et les autres kinds du design
ne sont pas implémentés.

## 4. Branches et WAP : fonctionnement et écarts

Le prototype associe `prod` à `main`, et les autres environnements à
`env_<nom>`. Créer une référence vers un snapshot existant réutilise ses
fichiers. Cela n’isole ni le schéma de table, ni ses propriétés globales,
ni les droits sur les objets. La [documentation Iceberg des
branches](https://iceberg.apache.org/docs/latest/branching/) explicite notamment
le schéma partagé entre branches.

| Chemin du prototype | Comportement et limite |
|---|---|
| Table existante | Écriture sur `wap`, audit du snapshot obtenu, puis déplacement de la référence cible. Le nom `wap` est partagé entre tentatives, ce qui ne protège pas deux runs concurrents. |
| Première création | Création et append sur `main` avant audit. Un veto supprime ensuite l’entrée catalogue, sans annuler une lecture déjà effectuée. Une première création en dev passe aussi par main. |
| Publication vers main | `set_current_snapshot` déplace la référence. Le code n’ajoute pas de contrôle d’ascendance métier à la promotion. |
| Publication vers une autre branche | Suppression puis recréation de la référence dans deux commits distincts. |
| Promotion de plusieurs modèles | Traitement séquentiel des tables. Un échec intermédiaire peut laisser un ensemble de versions partiellement promu. |

Le veto de la démo confirme que la production du scénario reste inchangée
après un audit échoué sur une table déjà publiée. Il ne prouve pas cette
garantie pour la première création ou la concurrence. Les [contre-épreuves
du prototype](experiments/prototype-counteraudit/README.md) reproduisent ces
limites sur des données temporaires.

Supprimer une branche ne supprime pas nécessairement ses snapshots et fichiers.
Le [banc Lakekeeper/OpenFGA](experiments/hemera-v2-review/README.md) a aussi
reproduit une lecture de staging avant publication puis après suppression de
la branche. Un grant de lecture sur toute la table n’est pas une frontière de
confidentialité suffisante.

## 5. Plans, entrées et historique

Le fingerprint actuel couvre le corps du modèle, sa matérialisation, les clés
de merge et les hashes des modèles amont. Il ne couvre pas tout le contrat.
Renforcer uniquement un audit SQL peut laisser le plan inchangé. La catégorie
`NON_BREAKING` est déclarée, mais la fonction de catégorisation ne la produit
pas dans le code observé.

Le state store SQLite décide quels fingerprints sont appliqués. Perdre ce
cache change le plan, alors que les données Iceberg subsistent. Les écritures
actuelles ne portent pas les propriétés `origin.*` permettant la reprise
cible. Aucun acquittement de source n’est implémenté dans ce prototype.

Les entrées ne sont pas résolues une fois pour tout le run. Une branche absente
retombe sur le `main` courant ; plusieurs lectures peuvent donc observer des
éditions différentes. Le contrat cible doit figer les entrées et refuser un
pin manquant, sauf règle de résolution explicitement déclarée au plan.

`history()` liste les snapshots physiques et `scan_at()` accepte un identifiant
de snapshot. Ils ne distinguent pas encore éditions publiées, candidats et
snapshots rejetés. Le time travel gouverné devra vérifier la publication
historique, les droits actuels et la disponibilité des fichiers. L’historique
des snapshots ne constitue pas, seul, un registre de publications.

## 6. Le contrat de publication cible

Ce protocole est une proposition à implémenter dans les cœurs Rust partagés.
Il est détaillé dans la [décision
EL-4](../docs/hemera-v2/09-decision-el4-wap.html) et le [visuel édition,
publication et acquittement](../docs/hemera-v2/visuels/04-edition-publish-ack.html).

1. Le plan fixe les entrées, le contrat, les audits, l’identité, les limites et
   la plage source. Chaque tentative reçoit son propre staging privé.
2. Le writer crée un snapshot candidat avec `origin.cursor`, l’état de reprise
   et la provenance dans son summary. Un champ auto-déclaré ne lui donne pas
   le statut publié.
3. Les audits portent sur ce candidat exact. Leur preuve immuable doit être
   conservée et liée au candidat. Son support durable et sa récupération
   font partie du protocole à qualifier ; un fast-forward ne réécrit pas le
   summary pour y ajouter après coup le résultat des audits.
4. Le publisher vérifie les droits, l’ascendance, l’UUID, les références et
   les versions de schéma/spec attendues. Un changement global de schéma
   impose une précondition de commit ou une revalidation explicite.
5. Le commit conditionnel établit la publication. Le contrôle des générations
   périmées doit agir au même point de décision ou bénéficier d’une
   sérialisation prouvée, failover compris. Le REST Iceberg propose des
   assertions sur UUID, refs et schéma, pas un fencing Hemera natif.
6. Le coordinateur retrouve un reçu de publication certain avant d’acquitter
   la source. Une réponse réseau perdue ne prouve pas que le commit a échoué.
   Un candidat seulement préparé n’autorise jamais l’acquittement.

Le [contrat REST Iceberg
épinglé](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.2/open-api/rest-catalog-open-api.yaml)
définit les assertions du catalogue. Il ne prouve ni le publisher applicatif,
ni la confidentialité des objets, ni le comportement d’un writer particulier.

Pour plusieurs sorties, une release est elle-même une édition Iceberg qui
référence les membres validés. Les consommateurs du groupe résolvent cette
release avant leurs lectures. Des déplacements successifs des `main` ne
rendent pas atomiques les lecteurs qui continuent de consulter chaque table
indépendamment.

## 7. Moteurs, gouvernance et exploitation

DuckDB exécute les scénarios locaux. Le runner charge les relations en Arrow ;
l’adaptateur Spark peut aussi les convertir en Pandas. Sa méthode de lecture
directe du catalogue ne démontre pas que le chemin principal l’utilise. La
localisation des données, les copies et les accès réseau doivent être qualifiés
sur le chemin réellement exécuté.

Partager un catalogue ne rend pas les moteurs interchangeables. Le banc a
trouvé des divergences Spark/DuckDB sur `substr('abc',0,2)` et sur des types.
Icegres/DataFusion, DuckDB et les candidats distribués sans JVM devront passer
une matrice de valeurs, types, schémas, deletes, ressources et erreurs. Aucun
client parlant un protocole compatible n’est déclaré substituable sur ce seul
critère.

Les lectures gouvernées passent d’abord par Query et Files, avec résolution
d’éditions publiées autorisées. L’accès natif attend une preuve équivalente
sur métadonnées, manifests, données et fichiers de suppression. Les états
non publiés restent privés, y compris après veto.

Le rollback ne peut ni rétracter un ack déjà envoyé, ni annuler un effet
externe ou une suppression physique. Le schéma partagé et les politiques
d’accès suivent leurs propres règles. Restaurer derrière le curseur acquitté
exige un journal couvrant l’écart, sinon une reprise contrôlée sous une
nouvelle époque source. Expiration et GC doivent préserver les éditions,
lectures, exécutions et sauvegardes encore retenues.

Migrer SQLite vers Lakekeeper demande configuration, authentification,
stockage, droits et campagnes de panne. Une modification YAML ne prouve pas
cette migration. Les [transactions multi-tables de
Nessie](https://projectnessie.org/guides/transactions/) sont des capacités de
son catalogue dont l’exposition dépend des moteurs ; elles ne doivent pas
être attribuées indistinctement à Polaris ou au format Iceberg.

## 8. Ordre de poursuite et vérification

Le [HANDOVER](../HANDOVER.md) fixe les six invariants et le backlog. L’ordre
retenu est d’implémenter EL-4, de fermer les critères de confidentialité,
publication concurrente et reprise, puis de construire EL-1 à EL-13 et
d’étendre les kinds. Les quatre contre-épreuves servent de cas de régression.
Le travail inclut les pins d’entrée, le staging unique, la reconstruction du
cache, les fingerprints de contrat et l’isolation de la compilation Python.

Flows porte les runs bornés et les workers fongibles. Icegres fournit des
composants de calcul et d’écriture à adapter ; Eidos produit des plans
sémantiques et d’action. L’ajout de STREAM, FILESET, MODEL, EMBEDDINGS,
FEATURESET et des contrats d’export ne doit pas créer une autre autorité de
publication. Les identités, clés, drafts, commandes et reçus d’effets externes
gardent leurs journaux et sauvegardes propres.

Pour vérifier le parcours local existant :

```bash
cd cleyrop-dm
python -m pip install -e . pyarrow pytest
python demo.py
python -m pytest -q
```

Le succès attendu des dix tests décrit cette suite. Les campagnes de sécurité,
de parité et de reprise ont leurs résultats distincts dans le document 10.
L’exécution des contre-épreuves réussit lorsqu’elle reproduit les écarts ;
elle ne valide pas les garanties produit correspondantes.
