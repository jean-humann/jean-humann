# Banc local de parité Hemera v2

Ce banc contient de nouvelles campagnes synthétiques du 2 octobre 2026. Il ne rejoue pas à l'identique les anciennes campagnes I1–I12. Il n'implémente pas Flows. Spark et Keycloak sont des dépendances transitoires du banc ; la plateforme finale reste sans JVM.

Les résultats exécutés sont dans `evidence/results.json`, avec un JSON par campagne. Les statuts décrivent la sonde et sa portée. Un test de détection de divergence peut passer alors que la parité est refusée. Le script produit donc un bilan structuré ; son code de sortie ne constitue pas un gate de production.

## Versions et sources

| Composant | Version exécutée |
|---|---|
| Lakekeeper | 0.12.0 |
| OpenFGA | 1.8.16, modèle Lakekeeper `collaboration-4.3` |
| PostgreSQL | 16.15 |
| SeaweedFS | 4.36, stockage S3 local |
| Keycloak | 26.7.4, comptes de service synthétiques |
| Spark Connect | serveur, client léger et client complet 4.1.2 |
| Iceberg Java | runtime Spark 4.1 et AWS bundle 1.11.0 |
| PyIceberg | 0.12.0 |
| DuckDB / SQLGlot / cloudpickle | 1.5.6 / 30.12.0 / 3.1.2 |
| Arrow | 25.0.1 |
| Python | catalogue Linux 3.12.13 ; clients Spark 3.10.19 ; worker Spark 3.10.12 |

Les digests des images exécutées figurent dans `evidence/images.json` et dans `compose.yaml`. Les quatre fichiers `requirements-*.txt` verrouillent les dépendances Python. Les deux jars ont des SHA-256 dans `jars.sha256`. Le banc a tourné sur Docker Linux aarch64.

La chaîne OIDC/OpenFGA reprend l'[exemple officiel Lakekeeper au tag v0.12.0](https://github.com/lakekeeper/lakekeeper/blob/v0.12.0/examples/access-control-simple/docker-compose.yaml), commit `06f2876cfd2bcb29b6b8fa66de57034a3a79725b`. Son modèle est [versionné dans le même tag](https://github.com/lakekeeper/lakekeeper/blob/v0.12.0/authz/openfga/v4.3/schema.json). Le bootstrap suit la [documentation du tag](https://github.com/lakekeeper/lakekeeper/blob/v0.12.0/docs/docs/bootstrap.md). Le pull de l'image MinIO de cet exemple a été refusé par le registre ; le banc utilise SeaweedFS, aussi employé par l'[exemple officiel courant](https://github.com/lakekeeper/lakekeeper/tree/main/examples/minimal). Les jars viennent du [dépôt Maven Apache Iceberg](https://repo.maven.apache.org/maven2/org/apache/iceberg/). Le comportement de retry se vérifie dans le [code PyIceberg 0.12.0](https://github.com/apache/iceberg-python/blob/pyiceberg-0.12.0/pyiceberg/table/__init__.py).

## Exécution et nettoyage

Prérequis : Docker Compose, `uv`, `curl`, Python 3 et `shasum`. Copier ce dossier dans un emplacement jetable. Ne pas le lancer sur une installation existante. Les ports 15432, 18080, 18081, 18181, 18333 et 15003 doivent être libres.

```sh
bash scripts/run.sh
```

Le script installe les environnements isolés, vérifie les SHA-256 des jars, démarre les services, exécute les sondes et nettoie les conteneurs/volumes à la sortie. Les fichiers JSON restent dans `evidence/`. Le script refuse de démarrer si des ressources Compose du même projet existent déjà. Les contrôles locaux de lancement et de nettoyage ont été durcis après le banc ; ils ont été vérifiés séparément, sans rejouer les campagnes. Pour nettoyer explicitement un banc interrompu :

```sh
bash scripts/cleanup.sh
```

Ce nettoyage se limite au projet `hemera-v2-review`. Il vérifie le label des conteneurs connus avant de supprimer le projet et ses volumes. Il n'exécute aucun prune global et ne supprime aucune image. Les images téléchargées et les environnements Python peuvent rester en cache. Les services ont des limites CPU/mémoire et tous les ports publiés écoutent uniquement sur loopback. Les credentials `hemera-v2-review-local-only` sont des constantes publiques de test créées pour ce banc. Aucun secret existant, kubeconfig ou cluster distant n'est utilisé.

`run.sh` a été validé syntaxiquement ; ses commandes ont été exécutées par étapes pendant la campagne. L'enchaînement complet depuis une machine vierge n'a pas été rejoué après assemblage. Le banc nécessite un réseau pour récupérer les images et dépendances verrouillées.

## Résultats qui changent le verdict

- `STAGING-ISOLATION` refuse la confidentialité du staging dans une même table. Un lecteur OIDC avec le seul grant OpenFGA `select` découvre le snapshot WAP et lit son payload via GET signé Lakekeeper avant publication, puis après suppression de la branche par snapshot-id. Il ne possède aucune clé S3. `main` reste inchangé. Une branche WAP n'est donc pas une frontière de confidentialité avec ce modèle.
- I1 observe le retry automatique des appends dans PyIceberg 0.12.0. La phrase historique « aucun retry » concernait 0.11.1. Avec `commit.retry.num-retries=0`, le conflit puis le refresh/reapply sont aussi vérifiés. Le nettoyage d'un manifeste abandonné émet un rejet 400 de signature sur le delete S3 ; la collecte des fichiers orphelins reste à qualifier.
- I2 montre un gagnant et un conflit lors de deux commits CAS. Après refresh, un repointage aveugle vers la branche perdante remplace pourtant la visibilité du gagnant. Le contrôle d'ascendance rejette ce déplacement. INT-3 conserve les deux ajouts avec un wrapper local, un verrou advisory transactionnel PostgreSQL, une vérification d'ascendance et le CAS du catalogue.
- AUTH prouve 200 pour l'administrateur, 401 sans token, 404 pour un tiers, puis 200 après grant et 404 après révocation. Les décisions OpenFGA sont réelles. Les campagnes catalogue utilisent le remote signing S3, sans credentials de stockage dans le client.
- INT-5 échoue : le modèle natif ne déclare aucune condition et refuse le tuple conditionnel avec `undefined condition`. Un modèle séparé OpenFGA évalue correctement trois instants autour d'une échéance. Cela ne valide ni le passage du contexte par Lakekeeper ni un purgeur.
- INT-1 échoue sur `substr('abc',0,2)`, qui donne `ab` dans Spark et `a` dans DuckDB, et sur le contrat de type de `unix_timestamp`, int64 contre double. La première sonde I6 mélangeait sérialisation et fuseaux. En UTC de bout en bout, `date_trunc` donne des tables Arrow identiques ; cet écart initial ne démontre pas un défaut moteur.
- I10/I11, les artefacts par session et les lectures PyIceberg/Spark passent sur leurs échantillons. INT-10 compare réellement les deux distributions : mêmes résultats SQL/UDF/Arrow, mais classes d'erreur `.rdd` différentes. Les sessions d'artefacts utilisent des identifiants fournis par le client et un bearer partagé ; aucun JWT par tenant ni refresh n'est validé.
- I12 vérifie trois workers, `SKIP LOCKED`, les dépendances, l'abandon d'un lease committé, sa reprise et le rejet d'une complétion obsolète. La transition de schéma ajoute une colonne nullable : Spark conserve son schéma chargé jusqu'à `REFRESH TABLE`.

## Portée et travail restant

Les données sont minuscules et synthétiques. Aucun résultat ne prouve l'atomicité multi-table, un fencing durable du commit de destination face à un zombie, le failover distribué, l'ack d'une source réelle ou l'absence de double effet métier. I12 fence la complétion SQL, pas le commit Iceberg. INT-3 est un wrapper de revue, pas l'orchestrateur cible.

INT-2, INT-4, INT-6, INT-7, INT-8 complet, INT-9 et INT-14 restent ouverts. Les conditions TTL isolées, les événements d'audit dans les logs et le démarrage local de Spark ne ferment pas ces gates. INT-11 à INT-13 sont définis dans le document 02, même s’ils ne figurent pas dans la table E-INT du document 05. Ils ne sont pas exécutés ici.

Avant acceptation : isoler le staging dans un objet ou espace dont les lecteurs ordinaires sont exclus, tester le commit fenced sous perte de lease, définir le contrat SQL des types/fuseaux et des erreurs, puis vérifier les identités et autorisations de bout en bout. Conserver un chemin de rollback vers la dernière édition publiée. Le retrait de Spark et Keycloak du banc de migration est un gate explicite vers la cible sans JVM.
