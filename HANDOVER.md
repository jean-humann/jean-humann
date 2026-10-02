# HANDOVER : Hemera v2 / cleyrop-dm

Dernière mise à jour : 2 octobre 2026. Dépôt `jean-humann/jean-humann`.

## 1. Contexte et cible retenue

Hemera v2 est la refonte de la plateforme data souveraine Cleyrop. Iceberg,
Lakekeeper et OpenFGA restent les fondations. Flows orchestre des datasets
déclarés par manifeste. L’édition publiée, snapshot Iceberg estampillé, est
l’autorité des données et des curseurs d’ingestion.

La demande confirmée impose **zéro JVM dans la cible finale**, y compris Spark,
Trino, Keycloak, Kafka/Strimzi, writer OLake, plugins, notebooks et outils de
maintenance. Les services produit ont un core Rust, avec contrôle et données
séparés. Python/SQL utilisateurs, interfaces TypeScript et exécutants Go/C++
restent possibles derrière ces contrats. Supprimer les JVM et transférer les
cores Python existants sont deux critères distincts.

Icegres fournit des composants Rust de query/write à adapter. Eidos fournit le
compilateur sémantique et les plans d’action. Aucun des deux ne constitue encore
une implémentation conforme de la frontière d’édition Hemera. La présente
livraison est une étude, une décision et des preuves reproductibles, pas une
migration des services de production.

## 2. État vérifié

Les lectures HANDOVER, index documentaire puis DESIGN ont précédé tout
changement. Sur le prototype initial `1ca3659`, un venv isolé a exécuté :

```bash
cd cleyrop-dm
python -m pip install -e . pyarrow pytest
python demo.py
python -m pytest -q
```

La démo complète passe et **10 tests passent**. Utiliser `python -m pytest`,
pas le binaire `pytest` du PATH. Le préflight emploie Python 3.13.14, PyIceberg
0.12.0, DuckDB 1.5.6, Arrow 25.0.1, SQLGlot 30.21.0 et pytest 9.1.1.

| Livrable | État et limite |
|---|---|
| Documents 01 à 07 | Copies historiques conservées, non modifiées. Leurs généralisations sont corrigées par les addenda. |
| [08, cible Rust sans JVM](docs/hemera-v2/08-plateforme-rust-sans-jvm.html) | Étude du laboratoire de référence, du monorepo, d’Icegres et d’Eidos ; 20 missions distinctes exécutées par vagues de trois. |
| [09, décision EL-4](docs/hemera-v2/09-decision-el4-wap.html) | Extracteur OLake Go encapsulé, writer/publisher Rust. Choix architectural tranché ; implémentation à réaliser. |
| [10, preuves et campagnes](docs/hemera-v2/10-preuves-et-campagnes.html) | Banc réel local : 33 entrées qui se recoupent, 18 passed, 5 failed, 10 not_executed. Reclassées en neuf familles de contrats, sans score de maturité. |
| [11, atlas visuel](docs/hemera-v2/11-atlas-visuel.html) | Huit HTML dédiés direction/technique, 16 SVG clair/sombre, huit PDF de deux pages, dossiers direction (3 pages) et complet (16 pages). |
| [Banc reproductible](cleyrop-dm/experiments/hemera-v2-review/README.md) | Lakekeeper/OpenFGA/OIDC/S3/Spark Connect réels, données synthétiques, preuves assainies et versions épinglées. Nettoyage terminé. L’enchaînement final assemblé n’a pas été rejoué intégralement. |
| [Contre-épreuves du prototype](cleyrop-dm/experiments/prototype-counteraudit/README.md) | Quatre écarts reproduits : visibilité avant premier audit, promotion divergente, audits/fingerprints/cache, import Python durant plan. Aucune garantie produit validée par ces sondes. |

Les constats qui changent la suite du travail :

- Un lecteur `select` sur une table du banc récupère les données staging par
  GET signé avant publication, puis après suppression de la branche. Main
  reste intact. Cette sonde ne déclenche pas elle-même un audit ; WAP-VETO est
  séparée. WAP protège la publication, pas automatiquement les octets.
- Le modèle natif Lakekeeper 0.12.0/OpenFGA testé refuse les conditions TTL.
  Un test OpenFGA isolé ne prouve pas l’intégration Lakekeeper.
- La parité Spark/DuckDB échoue sur des valeurs ou types. Le cas date_trunc
  initialement différent est réconcilié après normalisation UTC/Arrow.
- PyIceberg 0.12.0 réessaie certains appends concurrents. La généralisation
  historique « aucun retry » ne s’applique pas à cette version.
- Un lease ou un verrou local ne prouve pas le fencing au commit de destination
  pendant un failover. Les campagnes réelles ne ferment pas ce gate.
- Le droit Lakekeeper `modify` inclut `can_commit` et `can_drop`, sans
  séparation staging/main dans le modèle inspecté. Le worker générique ne le
  reçoit pas : un writer de confiance médie déjà les commits de staging.
- I4 prouve la persistance de `origin.state` sur le même handle, pas une
  reprise. I6 ne compare pas strictement les types ; I8 n’affirme pas de parité
  malgré son statut passed. Les WAP positifs partent d’un main initialisé.

La relecture demandée pour un public mixte a repris tout le corpus, corrigé le
corps de 08–10 et réécrit DESIGN en français. Les sept originaux restent
conservés ; le [registre de corrections](docs/hemera-v2/11-atlas-visuel.html#relecture)
rend leurs écarts explicites. Trois agents de la flotte initiale ont été
réutilisés pour l’architecture, les preuves et la cohérence éditoriale. La démo
et les dix tests ont été revérifiés avant modification (10 passed en 1,34 s).
Aucun banc réel n’a été relancé pour cette seconde livraison.

Les JVM Spark/Keycloak du banc sont transitoires. Aucun cluster client n’a été
modifié. Les arbres locaux Icegres/Eidos avec modifications utilisateur ont été
préservés ; aucun de leurs fichiers n’a été committé ici.

## 3. Les six invariants

1. **Destination autoritaire.** Curseurs, état de reprise et provenance vivent
   dans le `summary` du snapshot de la dernière édition publiée, `origin.*`.
   Ils sont attachés au candidat dès sa création. Une propriété globale de
   table, un state file ou PostgreSQL Flows ne remplace pas cette autorité.
2. **Publish-then-ack.** La source n’est acquittée qu’après la publication qui
   couvre sa plage. Une réponse de commit perdue se résout dans l’historique
   autorisé des publications, pas dans tous les snapshots ou tous les ancêtres
   du head. Si la preuve manque, bloquer et réconcilier. Un receipt de réception
   HTTP durable ne prétend pas être une publication métier.
3. **WAP partout.** Stage privé par tentative, audits du snapshot exact, puis
   publication conditionnelle avec ascendance, UUID, têtes et schéma/spec
   attendus. La preuve d’audit post-candidat doit être liée durablement ; un
   fast-forward ne réécrit pas son summary. Les fichiers audités sont immuables
   face au worker. Un veto ne crée aucune édition publiée. Il peut laisser des
   objets privés à nettoyer ; leur confidentialité est un contrat à tester.
4. **Journal rejouable.** Les flux éphémères entrent d’abord dans une capture
   durable. La rétention, la synchronisation disque et les domaines de panne
   font partie de la garantie. Un broker nommé ne la prouve pas.
5. **Tiers encapsulés.** OLake, dbt, SQLMesh et dlt sont des exécutants bornés.
   Ils ne publient pas directement, ne gouvernent pas les droits et ne décident
   pas du curseur. Le changement de moteur est un placement qualifié.
6. **Runs bornés, workers fongibles.** Pas de daemon de traitement par source.
   La capture protocolaire peut utiliser une passerelle mutualisée permanente.
   Une tentative périmée doit être empêchée de publier au point de commit.

Ces invariants remplacent les exceptions historiques STREAM avec audits après
publication et le bouton de publication forcée après veto. Une édition raw peut
passer ses audits d’intégrité puis autoriser l’ack ; les éditions métier aval
passent leurs propres audits avant publication.

FILESET, MODEL, VIEW et EMBEDDINGS ont aussi une édition Iceberg autoritaire de
données ou de manifeste. Leurs index/aliases sont dérivés. Une release de
plusieurs sorties est elle-même une édition Iceberg qui référence ses membres,
avec lecteurs épinglés et checkpoint commun (source, époque, plage,
participants) ; des promotions successives ne prouvent pas l’atomicité.

La taxonomie distingue huit kinds de datasets, EXPORT comme effet externe et
EXPOSURE comme déclaration de consommateur. SOURCE, OP et TEST sont des nœuds
de flow. La compaction peut publier sous WAP ; expiration et GC exigent un plan
audité, des racines de rétention et un journal de suppression. Une branche ne
permet pas d’annuler un effacement physique.

Les éditions reconstruisent les projections de données, mais pas les identités,
clés, drafts non publiés, commandes et reçus d’effets externes. Ceux-ci exigent
leur journal et leurs sauvegardes. Un rollback ne rétracte pas un ack source.
Restaurer derrière les acks impose de prouver la couverture du journal ou de
bloquer puis reconstituer la source sous une nouvelle époque.

## 4. Lecture et conventions documentaires

Lire [l’index](docs/hemera-v2/README.md) pour les douze documents et huit planches. Les sept HTML
initiaux restent les copies historiques de leurs publications. Les addenda
08 à 12 sont locaux ; aucune publication claude.ai nouvelle n’est annoncée.
Les six invariants et les addenda priment en cas de contradiction.

Le [DESIGN du prototype](cleyrop-dm/DESIGN.md) distingue désormais dans son corps
le comportement observé, les contre-épreuves et la cible. Ne pas convertir les tests locaux verts en
preuve de concurrence, de sécurité ou d’acquittement exactement une fois.

Les documents sont en français, autonomes, sans CDN, avec variables CSS
clair/sombre et SVG inline thémés. Valider balises, liens relatifs et ancres.
Si un original claude.ai est édité, télécharger sa version finale et réécrire
ses liens vers les copies locales selon la procédure de l’index. Les originaux
n’ont pas été modifiés par cette reprise.

Les planches sont générées depuis `docs/hemera-v2/visuels/content.py` et les
sources CSS/JS/SVG du même dossier. Ne pas éditer leurs HTML à la main. Le
[guide de reconstruction](docs/hemera-v2/visuels/README.md) et le
[rapport de validation](docs/hemera-v2/visuels/validation.json) décrivent
les contrôles navigateur, clavier, mobile, hors ligne et PDF. Ces contrôles
documentaires ne qualifient aucun mécanisme de production.

## 5. Backlog, dans l’ordre

1. **EL-4 : implémenter la décision du document 09.** Ne pas prolonger le
   sidecar Java dans la cible. Adapter extraction Go, writer Rust et publisher
   avec `PreparedWrite`, audits immuables, snapshot summary, receipt exact,
   CAS/ascendance et fencing. Le repli est un journal privé puis une édition
   brute sous WAP. Qualifier première création, TRUNCATE, transactions
   complètes, CTID/bootstrap, checkpoint vide et slot partagé.
2. **Fermer les gates I1–I12/E-INT encore ouverts.** Commencer par confidentialité
   staging, publication zombie/failover, crash publish/ack, TTL et droits
   complets, golden SQL. Le document 10 donne les statuts réels et les
   limites. Étendre au moteur Rust cible ; Spark reste une référence temporaire.
   Exécuter aussi les huit campagnes DR proposées dans le document 08.
3. **Implémenter EL-1…EL-13.** Premier lot EL-1/2/3/6 ; EL-8 avant toute dérive
   automatique. EL-5 et EL-9…13 réutilisent les contrats. EL-7 compare seulement
   des chemins qui satisfont les mêmes garanties. Voir la table détaillée du 08.
4. **Aligner le prototype puis le core partagé.** Corriger les quatre
   contre-épreuves ; stage unique, pins d’entrée, état relu de l’édition,
   fingerprints incluant le contrat, compilation isolée. Ajouter `source()` et
   STREAM/FILESET/EMBEDDINGS/MODEL/FEATURESET. Garder le prototype Python comme
   référence, sans le présenter comme le service Rust livré.
5. **Migrer les services et retirer les JVM par cohorte.** Façades compatibles,
   un propriétaire de schedule/publication/ack, parité de workloads et droits,
   restauration réelle, installation déconnectée, images/builds/maintenance
   sans JVM. Aucun moteur distribué ou IdP candidat n’est encore qualifié ici.

## 6. Travail Git

**Tout commit et push sur `claude/cleyrop-dataset-management-6lftkw`.**
Ne créer aucune pull request sans demande explicite. Messages descriptifs.
Préserver le travail utilisateur et ne pas modifier les dépôts sources locaux.
Ne pas publier leur code privé, credentials ou configurations clientes.

Pour le prototype, conserver le style existant et utiliser `python -m pytest
-q`. Les scripts d’expérience restent séparés de la suite produit ; les
contre-exemples ne doivent pas être comptés comme des tests produit verts.

## 7. Prompt de reprise

> Reprends Hemera v2 sur la branche imposée. Lis HANDOVER.md, puis
> docs/hemera-v2/README.md, puis cleyrop-dm/DESIGN.md dans cet ordre. Installe
> l’environnement, exécute la démo et les dix tests avant modification.
> Lis ensuite les addenda 08 à 10, l’atlas 11 et le dossier 12. Respecte les six invariants, la cible finale
> zéro JVM et le core Rust des services. Continue le backlog §5 dans l’ordre,
> en distinguant décision, implémentation et preuve. Committe et pousse sur la
> même branche, sans PR. Les gates de confidentialité, fencing et reprise
> restent ouverts malgré la démo verte.

## 8. Dossier détaillé des services et fonctionnalités

La demande de détail a produit le [dossier 12](docs/hemera-v2/12-dossier-services-fonctionnalites.html)
et son [portail](docs/hemera-v2/dossier/index.html). Il couvre les 22 dossiers
de services et les 34 composants de support recensés dans le monorepo. Chaque
fiche fonctionnelle distingue comportement observé, utilisateurs, interfaces,
états, dépendances, cible Rust, migration et critère d’acceptation. Icegres,
Eidos, la référence clonée, les contrats communs et la restauration disposent
de chapitres dédiés.

Les données structurées et la [couverture](docs/hemera-v2/dossier/coverage.json)
permettent de retrouver les sources et limites. L’annexe indexe 744 déclarations
statiques d’interfaces, y compris des préfixes partiels ; ce nombre ne décrit
pas les routes actives d’un déploiement. La couverture des dossiers de services
n’est pas une certification de tous les chemins ou configurations.

Préflight répété avant cette rédaction : démo réussie et 10 tests verts en
0,88 s. Aucun service source ni prototype modifié, aucun banc de production
exécuté. Les contrôles du [rapport documentaire](docs/hemera-v2/dossier/validation.json)
portent sur références, liens, couverture, navigateur et exports PDF. Voir le
[guide du dossier](docs/hemera-v2/dossier/README.md) pour reconstruire les fichiers.
