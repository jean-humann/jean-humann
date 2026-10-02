"""Reviewed content of the Hemera visual atlas. No external asset is required."""
from components import box, detail, lane, note, path, view

PAGES = []


def page(slug, title, lead, body, details, *, height=720, views=None,
         takeaways=(), contracts=(), sources=(), caption='', status='Cible proposée', **extra):
    PAGES.append(dict(slug=slug, title=title, lead=lead, svg=''.join(body),
                      height=height, details=details, initial=next(iter(details)),
                      views=views or [], takeaways=takeaways, contracts=contracts,
                      sources=sources, caption=caption, status=status, **extra))


page('01-carte-plateforme', 'Une plateforme, une frontière de publication',
     'Les services Rust organisent le travail. L’édition Iceberg publiée fixe ce que les utilisateurs peuvent lire et ce que les sources peuvent acquitter.',
     [lane(20,20,1160,145,'ACCÈS PRODUIT','Des façades compatibles pour les utilisateurs et les outils'),
      lane(20,190,365,470,'CONTRÔLE · SERVICES RUST','Identité, intention et exécution bornée'),
      lane(410,190,365,470,'DONNÉES · EXÉCUTANTS','Fichiers privés, requêtes et index dérivés'),
      lane(800,190,380,470,'PUBLICATION · SERVICES DE CONFIANCE','Un passage obligatoire vers l’édition'),
      path('client-control','M190 148 V178 H37 V320 H51'), path('client-query','M605 148 V178 H786 V517 H744','teal'),
      path('schedule','M350 442 H397 V322 H439'), path('prepare','M740 321 H833'),
      path('iam-flow','M200 365 V391'),path('eidos-flow','M200 520 V494','purple'),
      path('audit','M995 366 V470'), path('commit','M995 560 V685'),
      path('read','M605 560 V685','teal'),
      box('clients',55,78,'UI · SDK · SQL · MCP','Interfaces TypeScript et Python',w=1070,h=70,tag='CONTRATS STABLES'),
      box('iam',55,270,'IAM + Catalog','Droits, discovery, projections',w=295,h=95),
      box('flows',55,395,'Flows + Datasets','Manifestes, runs, contrats',w=295,h=95),
      box('eidos',55,520,'Eidos + Runtimes','Sémantique, actions, placement',w=295,h=95),
      box('workers',445,275,'Workers bornés','Écriture de fichiers privés',w=295,h=95),
      box('query',445,470,'Icegres + Files','Lecture d’éditions autorisées',w=295,h=95),
      box('writer',835,275,'Writer Rust','Commit staging contrôlé',w=310,h=95),
      box('publisher',835,470,'Audits + Publisher','Preuve, CAS, reçu, puis ack',w=310,h=95),
      note(455,407,'Pas de credential table.modify','dans un worker générique','red'),
      lane(20,683,1160,76,'FONDATIONS','Lakekeeper · OpenFGA · Iceberg / objets privés · PostgreSQL · journal durable')],
     {
      'flows':detail('Flows organise ; l’édition fait foi','Le scheduler possède l’intention et le suivi des runs, pas le curseur autoritaire.','PostgreSQL conserve commandes, leases et caches. La reprise relit origin.* depuis une édition publiée autorisée. Un worker prépare un résultat ; il ne peut ni publier main ni acquitter la source.'),
      'clients':detail('Conserver les usages','Les interfaces existantes migrent par contrat et par cohorte.','UI, SDK, SQL, notebooks et MCP passent par des façades compatibles. Les chemins directs vers le catalogue ou S3 doivent respecter la même autorisation par édition. Aucun raccourci réservé à un client ne contourne le publisher.'),
      'iam':detail('Droits et projections','IAM distribue les identités ; le Catalog produit des vues reconstruisibles des éditions.','OpenFGA évalue les relations. L’application de la politique se fait sur les accès effectifs aux éditions et à leurs objets. Les identités, clés et commandes ont leurs propres sauvegardes ; elles ne se reconstruisent pas toutes depuis Iceberg.'),
      'eidos':detail('Eidos transforme le sens en plan','Le modèle sémantique devient un plan épinglé que Flows peut exécuter.','Eidos compile types, concepts et actions. Runtimes choisit un exécutant qualifié. Le placement ne modifie ni l’autorité de publication, ni le checkpoint, ni les garanties requises.'),
      'workers':detail('Des capacités limitées à une tentative','Un worker peut produire des fichiers dans un espace privé.','Le droit Lakekeeper modify inclut can_commit et can_drop ; il ne sépare pas staging et main. Le contrat proposé retire ce droit aux workers génériques et fait médiatiser tous leurs commits par un writer de confiance. Fencing à implémenter et qualifier.','Mécanisme proposé'),
      'query':detail('Icegres sert des éditions autorisées','Un point de lecture peut associer moteur SQL, accès fichiers et index dérivés.','Le resolver lie identité, tenant, politique et pins d’entrée. Le service garde les credentials objets et vérifie la fermeture de fichiers accessible. Les API locales Icegres/Files restent à adapter ; aucun PEP complet n’est livré par cette étude.'),
      'writer':detail('Le staging est déjà une frontière de sécurité','Le writer transforme un PreparedWrite en candidat Iceberg sans laisser le worker modifier arbitrairement la table.','Validation de la tentative, du namespace, des fichiers autorisés, du schéma, de la ref et de origin.* avant commit. Avant audit, les capacités d’écriture et de suppression du worker sur les fichiers retenus sont retirées. Leur immuabilité doit résister aussi aux accès déjà émis. Le publisher est le seul chemin permis vers l’édition publiée. Cette séparation est applicative, pas un droit de branche natif démontré.','Mécanisme proposé à qualifier'),
      'publisher':detail('Une seule porte de publication','Le publisher lie candidat, preuve d’audit et publication conditionnelle.','Vérifier UUID, ascendance, têtes attendues, schéma/spec et autorité de tentative. Le CAS Iceberg ne fournit pas à lui seul un assert-fence. Un reçu reconstructible résout les réponses perdues. L’acquittement source vient après la publication.','À implémenter et qualifier','09-decision-el4-wap.html')},
     views=[view('Vue complète','','','Les blocs bleus sont la cible. Les fondations existent ; leur assemblage et ses frontières restent à qualifier.'),
            view('Parcours de lecture','clients iam query','client-query read','L’identité et les pins choisissent une édition ; le service de lecture contrôle les objets accessibles.'),
            view('Parcours de publication','clients iam flows workers writer publisher','client-control iam-flow schedule prepare audit commit','Le worker produit en privé. Le writer prépare le candidat. Le publisher autorise la visibilité puis l’ack.')],
     takeaways=[('Séparer les responsabilités','Flows planifie ; les services de données exécutent ; la publication engage la plateforme.'),('Partager le core Rust','Réutiliser les contrats d’édition, de politique et de reçu entre services.'),('Qualifier les fondations','Lakekeeper/OpenFGA ne fournissent pas seuls toutes les frontières dessinées.')],
     contracts=[('Contrat de service','Manifest, Run, PreparedWrite, AuditEvidence, PublicationReceipt et InputPins constituent les coutures à stabiliser.'),('Frontière de confiance','Le writer et le publisher ont des privilèges catalogue élevés. Leurs identités, accès réseau et chemins de commit doivent être fermés et testés.')],
     sources=[('Étude consolidée','../08-plateforme-rust-sans-jvm.html'),('Droits Lakekeeper 0.12.0','https://github.com/lakekeeper/lakekeeper/blob/v0.12.0/authz/openfga/v4.3/components/lakekeeper_table.fga')],
     caption='Architecture cible proposée · Chaque flèche représente un contrat, pas une intégration déjà livrée.',height=780)


page('02-avant-cible', 'Retirer la JVM sans perdre les usages',
     'La migration porte sur les services métier, les moteurs, l’identité et l’exploitation. Le changement de langage ne suffit pas à préserver les contrats.',
     [lane(20,20,420,660,'EXISTANT OBSERVÉ','Inventaire local Cleyrop et laboratoire de référence'),
      lane(510,20,670,660,'CIBLE ET DÉCISIONS','Cores métier Rust ; exécutants spécialisés encapsulés'),
      path('services','M414 148 H538'),path('engine','M414 286 H538'),path('identity','M414 428 H538'),path('operations','M414 573 H538'),
      box('kotlin',45,90,'6 services Kotlin / Spring','Collect, Dev, Model, Serve,',tone='teal',w=370,h=108,tag='OBSERVÉ',lines=['Collect, Dev, Model, Serve,','Process, Notification']),
      box('engines',45,232,'Spark · Trino · OLake Java','Calcul, requêtes, writer',tone='teal',w=370,h=108,tag='OBSERVÉ'),
      box('platform',45,374,'Keycloak · Kafka / Strimzi','Identité et transport',tone='teal',w=370,h=108,tag='OBSERVÉ'),
      box('hidden',45,516,'JVM dans les dépendances','Builds, images, maintenance, notebooks',tone='teal',w=370,h=108,tag='À INVENTORIER COMPLÈTEMENT'),
      box('cores',540,90,'Services produit Rust','Contrôle + données, domaines regroupés',w=605,h=108,tag='DÉCISION'),
      box('compute',540,232,'Icegres + writer Rust','Calcul distribué : qualification ouverte',w=605,h=108,tag='CIBLE / GATE'),
      box('idp',540,374,'IdP et journal sans JVM','ZITADEL / JetStream : candidats à qualifier',tone='amber',w=605,h=108,tag='CANDIDATS'),
      box('exit',540,516,'Installation sans JVM','Runtime + CI + maintenance + reprise',w=605,h=108,tag='CRITÈRE DE SORTIE')],
     {
      'cores':detail('Regrouper par contrat métier','La cible redécoupe les responsabilités, sans imposer une traduction fichier par fichier.','Les six services Kotlin sont inventoriés. Les cores Python métier migrent aussi vers Rust selon le périmètre produit. Python/SQL des utilisateurs et interfaces TypeScript restent possibles. Les adaptateurs et exécutants Go/C++ sont encapsulés.'),
      'kotlin':detail('L’existant porte des contrats à conserver','Les API et objets métier sont le point de départ du découpage.','Data-collect porte la collecte. Data-dev porte manifestes, versions, graphes et intégration Git, avec les environnements de développement. Data-model porte l’identité, les métadonnées et les contrats des datasets ; il ne se confond pas avec la couche sémantique Eidos. Data-serve porte les accès, process-data les runs et notification-center les notifications. Un service existant peut alimenter plusieurs domaines cibles.','Inventaire de code'),
      'engines':detail('Des remplacements par workload','Lire, transformer, écrire et maintenir Iceberg exigent des qualifications différentes.','Icegres/DataFusion et DuckDB ne promettent pas toute la sémantique Spark/Trino. Ballista ou Sail restent des candidats de calcul distribué. OLake est réutilisé côté extraction Go ; son writer Java sort de la cible.','Inventaire et décision'),
      'platform':detail('Identité et journal font partie de la migration','Le retrait JVM inclut les services tiers de la plateforme.','Migrer protocoles OIDC, droits, sessions et audit ; pour le journal, prouver la durabilité, le replay, la déduplication et la rétention avant de déplacer les acks. Aucune qualification complète des remplaçants n’a été exécutée ici.','Inventaire de code'),
      'hidden':detail('La sortie est aussi opérationnelle','Le critère final couvre ce qui s’installe, se construit, se restaure et se maintient.','Inventaire SBOM des images et dépendances transitives ; chemins notebook, Spark client, plugins, jar d’outillage, compaction et jobs de secours. Une JVM présente seulement dans un outil de reprise empêcherait encore l’acceptation finale.','Inventaire à compléter'),
      'compute':detail('Distinguer local et distribué','Icegres est une base locale réelle ; le calcul distribué reste à choisir sur preuves.','Qualifier SQL, Arrow, DML, annulation, mémoire, spill, schéma et WAP. Le repli OLake passe par un journal privé puis une édition raw auditée. Aucun moteur n’est accepté par seule compatibilité annoncée avec Iceberg.'),
      'idp':detail('Un candidat ne constitue pas une décision produit','ZITADEL et JetStream servent à instruire les besoins sans JVM.','ZITADEL : tokens, fédération, impersonation et politiques. JetStream : accusés, synchronisation, réplication, consommateurs et domaines de panne. Ces qualifications sont ouvertes ; Go est admis pour une brique tierce encapsulée.','Choix ouvert'),
      'exit':detail('Une bascule se signe sur des preuves','Les nouveaux chemins doivent couvrir usage, droits, données et reprise.','Une cohorte a un seul propriétaire d’écriture, de schedule et d’ack. Rollback applicatif et retour de données sont distincts : revenir avant des acks exige la couverture rejouable ou une reconstruction sous nouvelle époque.','Critère de sortie')},
     takeaways=[('Deux exigences distinctes','Zéro JVM dans tout le déploiement ; core Rust dans chaque service produit.'),('Conserver la valeur locale','Réutiliser Icegres et Eidos, après adaptation de leurs frontières.'),('Ne pas promettre de gain non mesuré','Coût, performances et délais restent à mesurer sur les workloads Cleyrop.')],
     contracts=[('Sélection des moteurs','Comparer seulement des configurations offrant les mêmes garanties de publication, de droits et de reprise.'),('Retrait vérifiable','Une installation neuve et une restauration sans JVM doivent fonctionner avant de clore le programme.')],
     sources=[('Inventaire et migration','../08-plateforme-rust-sans-jvm.html'),('Code du laboratoire de référence','https://github.com/sanderdw/iceberg-data-platform/tree/4506d8a')],
     caption='Inventaire ≠ cible déployée · Les candidats IdP, journal et calcul distribué ne sont pas qualifiés dans cette étude.',status='Inventaire + trajectoire proposée')


page('03-icegres-eidos', 'Icegres exécute. Eidos donne le sens.',
     'Les deux projets apportent des briques Rust utiles. Leur intégration passe par des éditions épinglées et le même contrôle de publication que les autres services.',
     [lane(20,20,1160,245,'LECTURE · DU SENS AU RÉSULTAT','Une requête se fixe sur une version du modèle et des éditions de données'),
      lane(20,290,1160,260,'ACTION · DE L’INTENTION À L’ÉDITION','Une action peut créer un run ; elle ne devient pas un raccourci vers main'),
      lane(20,575,1160,120,'ADAPTATIONS À LIVRER','Les composants locaux sont observés ; ces coutures de gouvernance restent à implémenter'),
      path('compile','M280 157 H328','teal'),path('resolve','M570 157 H618','teal'),path('execute','M860 157 H908','teal'),
      path('plan','M280 427 H328'),path('run','M570 427 H618'),path('publish','M860 427 H908'),
      box('model',45,108,'Eidos','Modèle + requête typée','teal',235,105,'BASE LOCALE'),
      box('pins',335,108,'Resolver','Identité + InputPins','blue',235,105,'À CONSTRUIRE'),
      box('icegres',625,108,'Icegres','SQL / DataFusion / Arrow','teal',235,105,'BASE LOCALE'),
      box('result',915,108,'Résultat gouverné','Éditions et modèle connus','blue',235,105,'CIBLE'),
      box('action',45,378,'Eidos ActionPlan','Intention, droits, idempotence','teal',235,105,'BASE À ADAPTER'),
      box('flows',335,378,'Flows','Run borné + worker privé','blue',235,105),
      box('candidate',625,378,'Writer + audits','Candidat exact, preuve liée','blue',235,105),
      box('edition',915,378,'Publisher','CAS → édition → ack','blue',235,105),
      note(45,657,'Eidos : authority + actions','Actif PostgreSQL / latest → pins d’édition','amber'),
      note(445,657,'Icegres : query + write','Direct sync / buffer → PreparedWrite','amber'),
      note(825,657,'Contrats communs','Politique · reçu · annulation','amber')],
     {
      'pins':detail('InputPins avant exécution','La réponse doit pouvoir expliquer quelles données et quelle définition l’ont produite.','Capturer l’édition du modèle sémantique, les UUID de tables, snapshot IDs ou release, la version du contrat et l’identité/politique. Les pins sont conservés pendant le run ; ni latest ni committed_at ne remplacent cette résolution.'),
      'model':detail('Ce qu’Eidos apporte','Le compilateur sémantique et le typage évitent de reconstruire cette couche.','Le code local possède une sémantique et des plans d’action réutilisables. Les états actifs PostgreSQL et les recherches du dernier commit ne satisfont pas encore l’autorité d’édition Hemera. Les publications de modèle doivent devenir des éditions de définition gouvernées.','Observé dans le code'),
      'icegres':detail('Ce qu’Icegres apporte','Le moteur Rust fournit une base de requêtes et d’écriture à intégrer.','Réutiliser les composants SQL/DataFusion, Arrow, accès catalogue et writer selon leurs capacités réelles. Les chemins locaux de synchronisation et d’écriture bufferisée ne démontrent pas WAP, le fencing ni un PublicationReceipt complet.','Observé dans le code'),
      'result':detail('Un résultat explicable','La réponse expose les pins qui ont servi à la calculer.','Contrat Flight/HTTP à compléter : identité d’utilisateur, tenant, politique, pins, erreurs et annulation. Le service de lecture applique les droits de ligne/colonne avant sortie. Le protocole Arrow n’apporte pas lui-même cette gouvernance.','Adaptation à livrer'),
      'action':detail('L’action Eidos reste une intention','Une action décrit un effet voulu et ses préconditions.','Un ActionPlan autorisé est soumis à Flows avec clé d’idempotence. Le code local n’offre pas encore une atomicité générale entre ses écritures ou effets. Distinguer données sous WAP et effets externes journalisés.','Observé + contrat cible'),
      'flows':detail('Un seul contrat d’exécution','Eidos et les autres clients déclenchent le même chemin de run.','L’ordonnanceur crée une tentative bornée, résout ses pins et attribue des capacités limitées. Une action utilisateur ne reçoit pas de credentials lui permettant de contourner la publication.'),
      'candidate':detail('Adapter la sortie du writer','PreparedWrite décrit la matière à publier sans publier lui-même.','Fichiers privés, schéma, partitionnement, origine et opération sont contrôlés par le writer de confiance. L’audit lie un snapshot exact et son contrat. Une preuve d’audit ne peut pas être ajoutée rétroactivement au summary par fast-forward.'),
      'edition':detail('Réutiliser une seule frontière','Le publisher est partagé avec les ingestions et transformations.','Pas de publisher Eidos concurrent, pas d’autorité de curseur Icegres séparée. La publication conditionnelle et le reçu reconstructible sont communs. Les caches d’éditions et les index Eidos sont des projections. Commandes, drafts, identités et reçus d’effets gardent leur journal durable et leurs sauvegardes.')},
     views=[view('Les deux parcours','','','Le vert désigne une base locale observée. Le bleu désigne le contrat Hemera à construire.'),view('Lecture','model pins icegres result','compile resolve execute','Le modèle et les données sont épinglés avant l’exécution ; le résultat conserve leur identité.'),view('Action','action flows candidate edition','plan run publish','Le plan d’action devient un run ; tous les chemins d’écriture passent par la publication contrôlée.')],
     takeaways=[('Réutiliser le code utile','Compiler, typer, lire, produire des fichiers et transporter Arrow.'),('Ajouter les coutures manquantes','Pins, politique, PreparedWrite et reçu de publication.'),('Garder une seule autorité','Ni l’état actif Eidos, ni le buffer Icegres ne décide de l’édition publiée.')],
     contracts=[('Premier lot conseillé','Un modèle Eidos épinglé lit une édition via Icegres ; une action produit un candidat privé puis une édition auditée.'),('Tests d’acceptation','Concurrent publish, perte de réponse, annulation, tenant, politique de ligne/colonne, modèle périmé et lecture à édition fixe.')],
     sources=[('Analyse des dépôts locaux','../08-plateforme-rust-sans-jvm.html'),('Écarts du prototype','../../../cleyrop-dm/experiments/prototype-counteraudit/README.md')],
     caption='Lecture de code locale · Icegres et Eidos n’ont pas été modifiés ou déployés par cette étude.',status='Réutilisation proposée')


def state(edition, cursor, ack, run, text, node):
    return dict(edition=edition,cursor=cursor,ack=ack,state=run,text=text,node=node)


start=state('E42','100','100','PRÉPARATION','L’édition publiée E42 porte le curseur 100. Une tentative couvre la plage 101–120, sans acquitter la source.','prepare')
staged=state('E42','100','100','STAGING','Le writer crée un candidat privé E43 avec origin.*. Ses snapshots ne sont pas encore des éditions publiées.','stage')
audited=state('E42','100','100','AUDITÉ','Une preuve immuable lie le candidat exact et le contrat d’audit. Son lien est vérifiable avant la publication ; aucun summary n’est réécrit par fast-forward.','audit')
published=state('E43','120','100','ACK_PENDING','Le CAS a publié E43. Le curseur autoritaire vaut 120 ; la source n’a pas encore confirmé son acquittement.','publish')
done=state('E43','120','120','TERMINÉ','Le reçu de publication permet l’acquittement idempotent. Un cache perdu se reconstruit depuis l’édition et l’historique autorisé des publications.','ack')

page('04-edition-publish-ack', 'Une édition avant chaque acquittement',
     'Le moment décisif est la publication conditionnelle. Un veto, un conflit ou une réponse perdue ne doivent jamais être interprétés comme une autorisation d’acquitter.',
     [lane(20,20,1160,280,'PRÉPARER EN PRIVÉ','Édition visible E42 · curseur 100 · ack source 100'),
      lane(20,350,1160,280,'PUBLIER, PUIS ACQUITTER','La ligne de visibilité change une fois ; la source suit ensuite'),
      path('p1','M370 165 H438'),path('p2','M755 165 H818'),path('p3','M1000 225 V400 H725 V433'),
      path('failure','M575 225 V326 H36 V495 H46','red',True),
      box('prepare',50,115,'1 · Préparer','Plage, opération, tentative',w=320,h=110,tag='E42 RESTE VISIBLE'),
      box('stage',445,115,'2 · Writer staging','Candidat E43 + origin.*',w=310,h=110,tag='SNAPSHOT PRIVÉ'),
      box('audit',825,115,'3 · Auditer','Preuve liée au snapshot exact',w=320,h=110,tag='AUCUNE PUBLICATION'),
      box('reject',50,440,'Veto / conflit','Aucune nouvelle édition','red',320,110,'REFUS OU RÉCONCILIATION'),
      box('publish',620,440,'4 · Publier','Préconditions + CAS',w=250,h=110,tag='E43 DEVIENT VISIBLE'),
      box('ack',910,440,'5 · Ack source','Après preuve de publication',w=240,h=110,tag='CHECKPOINT COUVERT'),
      path('p5','M870 495 H903'),
      note(50,674,'RÉPONSE PERDUE ≠ COMMIT ÉCHOUÉ','Rechercher une publication approuvée ; un snapshot candidat ou un cache absent ne suffit pas.','amber')],
     {
      'prepare':detail('Lire le dernier checkpoint publié','Le run part de E42, qui couvre la source jusqu’à 100.','Identifier source, époque, plage, participants, operation_id, tentative et fence. Une lease SQL ne prouve pas que le commit d’un ancien worker sera refusé. Les sources éphémères doivent déjà disposer d’un journal durable.','Contrat cible','09-decision-el4-wap.html'),
      'stage':detail('Créer un candidat sans visibilité métier','E43 existe comme snapshot privé. Le consommateur continue de lire E42.','Le writer de confiance crée la branche et le snapshot avec origin.*. Un worker sans table.modify ne peut pas changer main. La première création de table est un cas à qualifier séparément ; les preuves WAP positives actuelles partent d’un main déjà initialisé.','Mécanisme à qualifier','09-decision-el4-wap.html'),
      'audit':detail('Lier la preuve au candidat','L’audit porte sur le snapshot exact, ses entrées et son contrat.','Après création du candidat, produire une preuve immuable : UUID, snapshot ID, opération, contrat, résultats et hash. Le lien proposé utilise un objet préalloué immuable ou un manifeste de release ; ce mécanisme reste à implémenter et qualifier. Fast-forward ne réécrit pas le summary.','Contrat proposé à qualifier','09-decision-el4-wap.html'),
      'publish':detail('Contrôler ce qui a pu changer','La publication est conditionnelle à l’état attendu de la destination.','Contrôler UUID, main attendu, ref de tentative, ascendance, schéma/spec et droit de tentative. Les assertions REST disponibles ne constituent pas un assert-fence natif. Le refus d’un zombie au commit exige un mécanisme applicatif testé.','À implémenter','09-decision-el4-wap.html'),
      'ack':detail('Acquitter ce qui est réellement publié','ACK_PENDING est un état normal après une publication réussie.','Si la réponse source se perd, recommencer l’ack idempotent de la plage déjà publiée. L’autorité reste l’édition, pas le statut SQL du run. Plusieurs sorties exigent une release Iceberg avec checkpoint commun et lecteurs épinglés.','Contrat cible','09-decision-el4-wap.html'),
      'reject':detail('Refuser ou réconcilier','Le veto et le conflit empêchent cette tentative de publier. L’édition effectivement publiée, y compris par un concurrent, reste autoritaire.','Une réponse perdue exige une recherche. Résoudre l’operation_id dans les publications approuvées, pas dans tous les snapshots ni tous les ancêtres. L’absence d’un cache n’est pas la preuve d’une absence de publication. Si le résultat ne peut être établi, bloquer et réconcilier avant nouvel effet ou ack.','Contrat cible','09-decision-el4-wap.html')},
     height=730,
     scenarios={
      'normal':[start,staged,audited,published,done],
      'veto':[start,staged,state('E42','100','100','VETO','Le premier audit échoue. E43 peut laisser des fichiers privés à nettoyer, mais aucune édition publiée ni ack nouveau.','reject')],
      'conflit':[start,staged,audited,state('Édition concurrente','À relire','100','CONFLIT','La tête ou le contrat schéma/spec attendu a changé. Refuser le CAS ou revalider explicitement ; ne jamais repointer main aveuglément.','reject')],
      'reponse_perdue':[start,staged,audited,state('À résoudre','À relire','100','PUBLICATION_UNKNOWN','Le serveur peut avoir publié E43. Ne pas relancer aveuglément : résoudre le reçu dans l’historique autorisé des publications.','publish'),state('E43','120','100','PUBLICATION_CONFIRMÉE','Dans cet exemple, la recherche confirme la publication approuvée de E43 et sa plage. Sans cette preuve, la reprise resterait bloquée pour réconciliation.','publish'),done],
      'zombie':[start,staged,audited,state('E42','100','100','REFUS EXIGÉ','La tentative a perdu son autorité. Le publisher doit la refuser au commit. Ce gate n’est pas qualifié par le simple test de lease SQL.','reject')],
      'ack_pending':[start,staged,audited,published,state('E43','120','100 ou 120','ACK À RÉCONCILIER','La réponse à l’ack s’est perdue. E43 reste publiée ; réconcilier l’ack sans recréer de données.','ack'),done]},
     scenario_labels={'normal':'Publication normale','veto':'Veto d’audit','conflit':'Conflit de publication','reponse_perdue':'Réponse de commit perdue','zombie':'Tentative zombie','ack_pending':'Réponse d’ack perdue'},
     takeaways=[('Le curseur voyage avec l’édition','Le checkpoint devient visible avec les données qu’il couvre.'),('Un état inconnu exige une preuve','Timeout ne signifie ni réussite ni échec du commit.'),('Le refus doit exister au commit','Un lease expiré dans PostgreSQL ne bloque pas seul un writer zombie.')],
     contracts=[('Écriture et audit','Le summary du candidat contient origin.* avant audit. Le support proposé pour la preuve post-audit et son lien immuable restent à implémenter et qualifier.'),('Récupération et histoire','Ne compter comme éditions que les publications approuvées. Un ancêtre de main peut être un snapshot intermédiaire jamais publié.')],
     sources=[('Décision EL-4','../09-decision-el4-wap.html'),('Contrat REST Iceberg 1.11.0','https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/rest-catalog-open-api.yaml')],
     caption='Simulation pédagogique du contrat cible · Ces animations ne sont pas des résultats de tests.',status='Contrat cible · simulation')


page('05-securite-frontieres', 'WAP protège la visibilité. Il faut aussi protéger les octets.',
     'Le banc a montré qu’un lecteur autorisé sur une table pouvait atteindre les fichiers d’un candidat non publié, même après retrait de sa branche. La cible doit contrôler l’accès à une édition et à tous ses objets.',
     [lane(20,20,555,535,'CHEMIN REPRODUIT DANS LE BANC','Main reste intact ; la confidentialité staging échoue'),
      lane(600,20,580,535,'CHEMIN CIBLE À QUALIFIER','Identité + édition + fermeture de fichiers autorisés'),
      path('leak1','M295 186 V233','red'),path('leak2','M295 341 V388','red'),
      path('safe1','M890 186 V233'),path('safe2','M890 341 V388'),
      box('reader',55,88,'Lecteur : table.select','Autorisation au niveau de la table','red',485,105,'OBSERVÉ'),
      box('metadata',55,238,'Métadonnées + signer','Le snapshot staging reste découvrable','red',485,105,'OBSERVÉ'),
      box('leak',55,395,'GET des objets non publiés','Accès aussi après retrait de la branche','red',485,105,'ÉCHEC REPRODUIT'),
      box('principal',635,88,'Identité et politique','Utilisateur, tenant, édition demandée','blue',505,105),
      box('pep',635,238,'Service de lecture / PEP','Vérifie édition et fermeture d’objets','blue',505,105),
      box('objects',635,395,'Accès objets limité','Données, manifests, deletes, statistiques','blue',505,105),
      box('commit_right',45,590,'Autre frontière : le droit de commit','table.modify permet aussi can_commit et can_drop. Un worker générique ne doit pas le recevoir.','amber',1110,105,'CONTRAINTE DU MODÈLE NATIF')],
     {
      'leak':detail('La confidentialité a échoué dans le banc','Main reste inchangé ; les octets du candidat sont lisibles avant et après retrait de sa branche.','STAGING-ISOLATION utilise une identité lectrice réelle, découvre le candidat via métadonnées puis lit par URL signée. Cette sonde ne déclenche pas d’audit : le veto est testé séparément dans WAP-VETO. Supprimer la ref ne suffit pas à révoquer les objets ou URLs déjà accessibles. Le résultat porte sur la configuration testée.','Échec reproduit','10-preuves-et-campagnes.html'),
      'reader':detail('Un grant table ne désigne pas une édition','Les droits relationnels sont utiles, mais leur granularité doit correspondre à la frontière produit.','Le test AUTH montre grants et révocation au catalogue. Il ne prouve pas l’isolation des snapshots d’une même table. Une restriction de ligne/colonne ne peut pas protéger un utilisateur qui possède en parallèle un accès objet plus large.','Observation du banc','10-preuves-et-campagnes.html'),
      'metadata':detail('Les métadonnées donnent accès à d’autres chemins','Masquer une branche dans l’interface ne ferme pas l’accès aux fichiers.','Contrôler métadonnées, manifests, fichiers de données, delete files, statistiques et anciennes versions accessibles. Le signer doit vérifier le graphe de fichiers de l’édition autorisée, pas seulement l’appartenance au stockage de la table.','Écart constaté','10-preuves-et-campagnes.html'),
      'principal':detail('Porter l’identité jusqu’à l’accès effectif','Le tenant et la politique suivent la requête jusqu’aux données retournées.','Pas de service account partagé transformant implicitement toute requête en lecture administrateur. Qualifier token exchange, expiration, sessions longues et révocation. Les conditions TTL du modèle natif testé sont refusées.','Cible non qualifiée','10-preuves-et-campagnes.html'),
      'pep':detail('Appliquer la politique à une édition','Le service de requête ou Files tient la frontière entre l’utilisateur et les objets.','Résoudre une publication approuvée, calculer les objets nécessaires et appliquer droits de lecture, ligne et colonne. Interdire les chemins directs plus permissifs ; journaliser la décision. Un proxy seul, sans limitation des credentials et du réseau, n’est pas une preuve.','Mécanisme proposé'),
      'objects':detail('Autoriser une fermeture de fichiers','Le périmètre couvre tous les objets référencés par l’édition choisie.','URLs signées et credentials doivent être limités et expirants. Les accès déjà accordés ne sont pas instantanément rétractables. La politique de rétention conserve les fichiers requis par les éditions, releases, lecteurs épinglés et preuves.','Contrat à implémenter'),
      'commit_right':detail('Le droit staging n’est pas natif ici','La séparation entre écrire une tentative et publier main doit être construite.','Dans le modèle Lakekeeper 0.12.0, modify donne can_write_data, can_commit et can_drop. Il n’existe pas dans ce modèle de permission par ref. Le contrat proposé fait passer les commits staging par le writer de confiance et la publication par le publisher. Il retire avant audit les capacités du worker à écraser ou supprimer les objets retenus, y compris via un accès déjà émis. Médiation et immuabilité effective restent à tester.','Modèle vérifié ; protection cible à qualifier')},
     takeaways=[('Séparer deux garanties','Un candidat invisible dans main peut rester lisible dans le stockage.'),('Fermer tous les chemins','Catalogue, signer, URLs, credentials et réseau doivent suivre la même politique.'),('Tester les refus','Lire un candidat rejeté, publier avec un ancien lease, traverser un tenant et conserver une URL après révocation.')],
     contracts=[('Acceptation confidentialité','Avec identité non privilégiée, aucune récupération des objets hors édition autorisée, avant et après veto, suppression de branche et expiration.'),('Acceptation publication','Un worker compromis ou périmé ne peut pas publier main, changer un schéma global ni supprimer une table via son accès staging.')],
     sources=[('Résultats AUTH et STAGING-ISOLATION','../10-preuves-et-campagnes.html'),('Modèle natif Lakekeeper 0.12.0','https://github.com/lakekeeper/lakekeeper/blob/v0.12.0/authz/openfga/v4.3/components/lakekeeper_table.fga')],
     caption='Rouge : comportement reproduit dans le banc local · Bleu : frontière proposée, encore à qualifier.',status='Échec observé + correction proposée')


page('06-kinds-provenance', 'Huit types de datasets, une autorité d’édition',
     'Tables, fichiers, modèles et index suivent le même principe de publication. L’export est un effet externe qui consomme une édition ; il n’ajoute pas un neuvième dataset.',
     [lane(20,20,1160,170,'DONNÉES TABULAIRES','Le snapshot publié porte les données et leur provenance'),
      lane(20,215,1160,170,'DÉFINITIONS ET ARTEFACTS','Le snapshot peut publier un manifeste plutôt que les octets de l’artefact'),
      lane(20,410,1160,170,'DÉRIVÉS POUR L’USAGE','Les index et stores sont des projections d’une édition autoritaire'),
      lane(20,605,1160,130,'EFFETS EXTERNES','Une autre forme de reprise : journal d’effets, idempotence et réconciliation'),
      box('table',45,92,'TABLE','Résultat tabulaire',w=350,h=75),
      box('incremental',425,92,'INCREMENTAL','Évolution incrémentale',w=350,h=75),
      box('stream',805,92,'STREAM','Raw publié par lots bornés',w=350,h=75),
      box('view',45,287,'VIEW','Définition versionnée',w=350,h=75),
      box('fileset',425,287,'FILESET','Manifeste + objets privés',w=350,h=75),
      box('model',805,287,'MODEL','Manifeste + artefacts',w=350,h=75),
      box('embeddings',45,482,'EMBEDDINGS','Édition source → index',w=350,h=75),
      box('features',425,482,'FEATURESET','Offline → store en ligne',w=350,h=75),
      note(825,516,'SOURCE · OP · TEST','Nœuds de flow, pas des kinds','amber'),
      box('export',45,657,'EXPORT','Édition consommée → livraison externe + reçu','amber',1110,72,'EFFET')],
     {
      'stream':detail('STREAM conserve WAP','Le raw forme des éditions bornées, auditables et rejouables.','La capture protocolaire peut être mutualisée et permanente ; les traitements restent des runs bornés. Les audits d’intégrité du raw précèdent sa publication et l’ack. Les audits métier aval s’appliquent à leurs propres éditions.','Contrat cible','09-decision-el4-wap.html'),
      'table':detail('TABLE','Le résultat d’une transformation forme une édition Iceberg.','Le manifeste déclare entrées, schéma, contrat et audits. L’édition conserve les pins d’entrée et la provenance. Un veto n’autorise pas de bouton « forcer la publication ».'),
      'incremental':detail('INCREMENTAL','L’opération incrémentale publie un nouvel état complet de référence.','Un curseur n’est jamais validé par un simple succès de worker. Upsert, deletes et checkpoint vide doivent préserver les transactions de source et être testés avec le moteur cible.'),
      'view':detail('VIEW','La définition, son contrat et ses références ont une édition autoritaire.','Le manifeste publié peut décrire une vue logique. Ne pas inventer un snapshot de données matérialisées lorsqu’il n’existe qu’une définition. Les entrées sont résolues selon un contrat explicite de pins.'),
      'fileset':detail('FILESET','Le manifeste Iceberg gouverne les fichiers publiés.','Les blobs peuvent vivre dans le stockage objet ; l’édition publie leur manifeste, les hashes et le contrat d’accès. Le listing de bucket et PostgreSQL ne constituent pas l’autorité de version.'),
      'model':detail('MODEL','Poids, signature et code d’inférence sont publiés comme artefacts référencés.','Le manifeste lie les objets immuables, données d’entraînement, évaluations et contrat. Le registre dérive les versions depuis les éditions. Les choix d’alias, de déploiement et de routage nécessitent aussi une spécification désirée et un journal de contrôle ; secrets et commandes ont leurs sauvegardes.'),
      'embeddings':detail('EMBEDDINGS','L’index est reconstruit depuis une édition publiée.','Version du modèle, entrées et vecteurs sont épinglés. Le proxy vérifie tenant, politique et édition ; le nom d’un index ou un alias de moteur vectoriel ne suffit pas à faire autorité.'),
      'features':detail('FEATURESET','L’offline publié fixe ce que le store en ligne doit servir.','Le store en ligne est une projection avec watermark d’édition. Documenter fraîcheur, cohérence, retard et reconstruction. Une écriture online réussie ne publie pas silencieusement une nouvelle édition.'),
      'export':detail('EXPORT est un effet','Il consomme une édition et produit une livraison externe.','Conserver clé d’idempotence, destinataire autorisé, édition consommée, résultat et reçu dans un journal durable. Une EXPOSURE déclare un consommateur, comme un dashboard ; elle ne déclenche pas nécessairement un export. Un rollback de dataset ne rétracte pas un fichier téléchargé, un webhook émis ni un ack source.','Clarification de taxonomie')},
     height=760,
     takeaways=[('Une règle pour huit kinds','Données ou manifeste : l’édition publiée reste l’autorité.'),('Des projections remplaçables','Index, alias et stores dérivés se reconstruisent depuis les éditions.'),('Des effets à réconcilier','Les systèmes externes ont besoin de reçus et d’idempotence, pas d’une promesse de rollback global.')],
     contracts=[('Maintenance','La compaction peut publier une nouvelle édition sous WAP. Expiration et GC utilisent un plan audité puis une suppression protégée : une branche ne peut pas annuler un effacement physique.'),('Provenance','Une maintenance conserve le checkpoint source couvert et ajoute sa provenance d’opération. Elle ne se présente pas comme une nouvelle plage ingérée.')],
     sources=[('Kinds, contrats et maintenance','../08-plateforme-rust-sans-jvm.html')],
     caption='Taxonomie cible : 8 kinds de datasets ; EXPORT est un effet, EXPOSURE déclare un consommateur. SOURCE, OP et TEST décrivent le flow.')


page('07-migration-decisions', 'Migrer par preuves et par cohortes',
     'Le chemin critique est la frontière d’édition. Les migrations d’identité, de journal et de calcul avancent en parallèle, puis se rejoignent sur une installation complète sans JVM.',
     [lane(20,20,1160,160,'DÉCISIONS DÉJÀ FIXÉES','Les choix ouverts portent sur les mécanismes et les candidats, pas sur ces exigences'),
      lane(20,210,1160,275,'CHEMIN CRITIQUE','Un gate se ferme par une preuve exécutée et conservée'),
      lane(20,515,1160,185,'QUALIFICATIONS EN PARALLÈLE','Pas de calendrier annoncé avant mesure des écarts et des workloads'),
      box('decisions',45,90,'Zéro JVM · cores Rust · éditions autoritaires','WAP · publish-then-ack · journal durable · exécutants bornés',w=1110,h=72,tag='DÉCIDÉ'),
      path('g1','M282 370 H328'),path('g2','M572 370 H618'),path('g3','M862 370 H908'),
      box('boundary',45,305,'1 · Frontière d’édition','Writer / publisher / preuves','amber',237,122,'GATE OUVERT',lines=['Writer / publisher / preuves','Confidentialité et reprise']),
      box('el',335,305,'2 · Premier EL réel','Source → raw → ack','amber',237,122,'APRÈS GATE 1',lines=['Source → raw → ack','C1–C4 corrigés, EL-1/2/3/6']),
      box('cohorts',625,305,'3 · Cohortes métier','Icegres, Eidos et services','amber',237,122,'PAR CONTRAT',lines=['Icegres, Eidos et services','API, données, droits, reprise']),
      box('zero',915,305,'4 · Sortie JVM','Installation + exploitation','amber',237,122,'ACCEPTATION FINALE',lines=['Installation + exploitation','Restauration et workloads']),
      box('identity',45,588,'Identité','OIDC, tenants, droits, TTL','amber',350,87,'CHOIX OUVERT'),
      box('journal',425,588,'Journal','Durabilité, replay, ack','amber',350,87,'CHOIX OUVERT'),
      box('distributed',805,588,'Calcul distribué','SQL, mémoire, DML, erreurs','amber',350,87,'CHOIX OUVERT')],
     {
      'boundary':detail('Le lot qui conditionne les autres','Construire la publication contrôlée et prouver ses refus.','Cas requis : première table privée, worker sans accès main, candidat rejeté illisible, CAS concurrent, schéma concurrent, fence zombie, perte de réponse et reprise à cache vide. Un simple verrou local ne ferme pas le gate.','Priorité 1'),
      'decisions':detail('Ce qui ne reste pas à arbitrer','La cible finale exclut toute JVM et conserve les six invariants.','EL-4 est tranché : extraction OLake Go encapsulée, writer/publisher Rust. Si le writer direct n’est pas disponible, journal privé puis raw sous WAP. Pas d’exception STREAM publiant avant audit.','Décision confirmée','09-decision-el4-wap.html'),
      'el':detail('Un vertical complet avant généralisation','Prouver une source réelle jusqu’à l’ack, avec fautes injectées.','EL-1/2/3/6 d’abord, EL-8 avant dérive automatique. Qualifier transactions complètes, TRUNCATE, bootstrap/CTID, checkpoint vide et source partagée. Le prototype Python fournit des contre-exemples à fermer, pas le service Rust final.','Priorité 2'),
      'cohorts':detail('Une cohorte, un propriétaire d’écriture','Basculer des usages complets avec un point d’autorité explicite.','Conserver façades compatibles ; shadow read possible. Un seul propriétaire de schedule, publication et ack. Séparer rollback logiciel, données et effets externes. Les changements de schéma suivent Expand / Migrate / Contract.','Trajectoire proposée'),
      'zero':detail('Le critère final est opérationnel','Une installation neuve et une restauration doivent fonctionner sans JVM.','Contrôler SBOM, images, CI, maintenance et notebooks. Rejouer workloads et politiques sur moteurs finaux. Aucun test Spark/Keycloak du banc transitoire ne vaut acceptation de leurs remplaçants.','Gate final ouvert'),
      'identity':detail('Qualifier avant déplacement des comptes','La compatibilité OIDC ne couvre pas tous les parcours de droits.','Tester fédération, refresh, échange de sujet, révocation, sessions longues, comptes techniques et reprise des clés. ZITADEL est un candidat de l’étude, pas une sélection validée.','Choix ouvert'),
      'journal':detail('Prouver le replay sous panne','Le journal doit couvrir les données déjà reçues et la restauration après ack.','Tester disque, réplication, rétention, pertes et doublons. Le reçu durable HTTP et le checkpoint métier sont distincts. Une restauration derrière un ack bloque si le journal ne couvre plus la plage.','Choix ouvert'),
      'distributed':detail('Choisir sur workloads comparables','La syntaxe compatible ne garantit pas la même sémantique.','Types, NULL, timezones, DML, erreurs, UDF, mémoire et annulation sont des critères d’acceptation. Ballista/Sail ou autre candidat sans JVM doivent être évalués avec les mêmes contrats. Aucun benchmark final n’a été exécuté.','Choix ouvert')},
     takeaways=[('Financer le chemin critique','Le publisher et les frontières de sécurité servent tous les services.'),('Découper par usage','Une cohorte doit pouvoir être exploitée et restaurée de bout en bout.'),('Accepter sur preuves','Pas de date ferme ni de gain chiffré sans qualification et mesure.')],
     contracts=[('Reprise','Rétablir clés, identités, commandes et journaux en plus des éditions. Reconstituer le checkpoint depuis les publications autorisées, puis vérifier la couverture des acks.'),('Gouvernance de décision','Chaque gate possède scénario, environnement épinglé, preuve conservée et décision. Un candidat reste ouvert tant que ces éléments manquent.')],
     sources=[('Backlog de reprise','../../../HANDOVER.md'),('Trajectoire détaillée','../08-plateforme-rust-sans-jvm.html'),('Gates et campagnes','../10-preuves-et-campagnes.html')],
     caption='Dépendances de migration, sans calendrier estimé · Tous les gates de qualification cible ci-dessus restent ouverts.',status='Trajectoire proposée')


evidence_rows=[
 ('publication','Publication WAP','CAS et staging après initialisation','Première table, zombie, crash / ack','amber'),
 ('authorization','Confidentialité','Candidat non publié lisible','Fermer l’accès aux objets non publiés','red'),
 ('expiry','Expiration des droits','TTL natif Lakekeeper refusé','Intégrer modèle, contexte et caches','red'),
 ('sql_semantics','Parité SQL','Valeurs et types divergent','Contrat sémantique des moteurs finaux','red'),
 ('execution','Exécution et clients','Sous-ensemble Spark transitoire','Clients, tenants et moteurs sans JVM','amber'),
 ('schema','Schéma et lectures','Ajout nullable / refresh observés','Contraction, concurrence et Icegres','amber'),
 ('orchestration','Livraison et leases','Complétion SQL obsolète refusée','Fencing destination et replay réel','amber'),
 ('retention','Rétention et GC','Propriété de rétention persistée','Expiration et purge physique sûres','amber'),
 ('planning','Plan et compilation','Import, cache et contrat en défaut','Manifestes, fingerprints et wrappers','red')]


def evidence_row(i, key, title, observed, missing, tone):
    y=112+i*61
    return (f'<g class="node {tone}" data-node="{key}" tabindex="0" role="button" aria-label="{title}" aria-pressed="false">'
            f'<rect class="node-bg" x="25" y="{y}" width="1150" height="53" rx="8"/>'
            f'<rect class="accent" x="25" y="{y+9}" width="4" height="35" rx="2"/>'
            f'<text class="node-title" x="43" y="{y+33}">{title}</text>'
            f'<text class="sub" x="346" y="{y+33}">{observed}</text>'
            f'<text class="sub" x="776" y="{y+33}">{missing}</text></g>')


page('08-preuves-risques', 'Les preuves se lisent par contrat',
     'Le banc apporte des résultats utiles et plusieurs refus nets. Il ne qualifie pas encore la plateforme cible : chaque contrat conserve ses limites et ses essais manquants.',
     [note(43,45,'33 entrées de registre, avec recouvrements','18 passed · 5 failed · 10 not_executed — aucun score de maturité'),
      note(43,96,'CONTRAT'),note(346,96,'OBSERVATION LIMITÉE'),note(776,96,'PREUVE QUI MANQUE')]
     +[evidence_row(i,*r) for i,r in enumerate(evidence_rows)]
     +[note(43,707,'À PART : PROTOTYPE','Démo + 10 tests existants verts ; 4 contre-exemples reproduits, 0 garantie produit acceptée.','amber')],
     {
      'publication':detail('Publication conditionnelle et WAP','Les mécanismes ont été sondés ; la reprise complète reste ouverte.','I1/I2/I3/I4, WAP-VETO et INT-3 se recoupent. I4 écrit origin.state puis le relit sur le même handle : aucune perte de cache ni reprise de processus. Les WAP positifs partent d’une table initialisée. C1/C2 montrent première visibilité et promotion divergente du prototype.','Partiel, avec contre-exemples','10-preuves-et-campagnes.html','famille-publication'),
      'authorization':detail('Autorisation et confidentialité','Grants/révocations fonctionnent ; le staging n’est pas confidentiel dans ce banc.','AUTH et STAGING-ISOLATION sont exécutés. INT-2, INT-6 et INT-14 ne le sont pas. Les tests absents couvrent notamment identité utilisateur/tenant, token exchange et politiques SQL.','Confidentialité refusée','10-preuves-et-campagnes.html','famille-authorization'),
      'expiry':detail('Expiration des droits','Le test OpenFGA isolé et l’intégration native donnent des résultats différents.','OPENFGA-TTL accepte/refuse des contextes temporels fournis dans un store séparé. INT-5 constate que le modèle natif Lakekeeper rejette la condition. Aucun TTL intégré de bout en bout n’est validé.','Intégration native refusée','10-preuves-et-campagnes.html','famille-expiry'),
      'sql_semantics':detail('Parité SQL','Plusieurs cas de bord produisent des écarts.','I6 ne compare pas strictement les types. INT-1 utilise schémas/valeurs Arrow et normalise UTC. I8 est marqué passed sans assertion de parité : sa propre observation comporte une divergence substr à zéro. Ne pas le compter comme équivalence réussie.','Parité refusée sur échantillon','10-preuves-et-campagnes.html','famille-sql-semantics'),
      'execution':detail('Exécution, clients et sessions','Des parcours Spark Connect réels fonctionnent sur un périmètre borné.','I9/I10/I11 et SPARK-ARTIFACTS couvrent closure, SQL, UDF, Arrow et artefacts par session. INT-10 observe des classes d’erreur différentes. INT-7 Kubernetes/operator n’est pas exécuté. Spark est une référence transitoire exclue de la cible finale.','Partiel sur moteur transitoire','10-preuves-et-campagnes.html','famille-execution'),
      'schema':detail('Lectures et évolution du schéma','L’ajout d’une colonne nullable et le refresh ont été observés.','MULTI-ENGINE et SCHEMA-TRANSITION réutilisent la table I3. INT-8 complet n’a pas été exécuté. Ni contraction, ni matrice Icegres, ni lecteurs concurrents ne sont qualifiés.','Expand seulement, partiel','10-preuves-et-campagnes.html','famille-schema'),
      'orchestration':detail('Ordonnancement et livraison durable','Une complétion SQL périmée est refusée ; cela ne bloque pas encore un commit Iceberg zombie.','I12 teste une file PostgreSQL synthétique avec trois threads. INT-4 livraison durable/pertes/doublons n’est pas exécuté. Les effets externes et le fencing destination demandent leurs propres scénarios.','Complétion SQL seulement','10-preuves-et-campagnes.html','famille-orchestration'),
      'retention':detail('Rétention et nettoyage','I5 démontre que la propriété est conservée dans les métadonnées.','Aucune expiration planifiée ou suppression physique n’a été validée. Tester les racines de rétention : publications, releases, lecteurs, preuves et replay. Le GC n’est pas annulé par un rollback de branche.','Métadonnée seulement','10-preuves-et-campagnes.html','famille-retention'),
      'planning':detail('Compilation, plan et adaptateurs','Lignage sur une requête ; contre-exemples sur le plan du prototype.','C3/C4 montrent audit renforcé ignoré, cache autoritaire et import avec effet de bord. I7 porte sur une requête AST. INT-9/11/12/13 restent non exécutés ; les wrappers tiers et la compilation isolée ne sont pas qualifiés.','Prototype en défaut sur ces contrats','10-preuves-et-campagnes.html','famille-planning')},
     height=755,
     takeaways=[('Ne pas additionner des garanties','Les sondes partagent tables, requêtes, bibliothèques et mécanismes.'),('Séparer observation et acceptation','Un script terminé peut avoir seulement persisté une propriété ou affiché un écart.'),('Conserver l’histoire des preuves','Les résultats bruts restent inchangés ; cette lecture en précise la portée.')],
     contracts=[('Prochain banc','Identifiant commun de run, commits réellement mesurés, versions serveur détectées, répertoire de résultats isolé et journal d’exécution complet.'),('Limite de reproduction','Le banc précédent a été exécuté par étapes. Son script final assemblé n’a pas été rejoué intégralement. Cette relecture n’a pas relancé les campagnes réelles.')],
     sources=[('Registre par famille','evidence-classification.json'),('Résultats et limites','../10-preuves-et-campagnes.html'),('Preuves brutes','../../../cleyrop-dm/experiments/hemera-v2-review/evidence/results.json')],
     caption='Familles de contrats, pas expériences indépendantes · Rouge : exigence en défaut dans le périmètre testé. Ambre : preuve partielle.',status='Audit des preuves conservées')


# Corrections found by the second review. The seven published originals remain intact.
ERRATA = [
 ('01 · Architecture', 'Leases, fingerprints, Catalog', 'Un lease ne prouve pas le fencing au commit. Le contrat complet participe au fingerprint. Le Catalog est une projection.', '01-architecture-flows-datasets.html', '04-edition-publish-ack'),
 ('02 · Développement', 'Kinds et PEP', 'FILESET a un manifeste Iceberg autoritaire. Huit kinds de datasets ; EXPORT est un effet. L’accès aux octets suit l’édition.', '02-modele-de-developpement.html', '06-kinds-provenance'),
 ('03 · Frontend', 'Veto et promotion', 'Aucun bouton ne force une édition après veto. La promotion exige des préconditions et un conflit explicite.', '03-design-frontend.html', '04-edition-publish-ack'),
 ('04 · Schéma', 'Moment de l’estampillage', 'Le summary du candidat est créé avant audit. Fast-forward ne lui ajoute pas rétroactivement un digest de preuve.', '04-annexe-schema-iceberg.html', '04-edition-publish-ack'),
 ('05 · Intégration', 'Retry, TTL, zombies', 'PyIceberg 0.12 peut réessayer certains appends. TTL natif refusé dans le banc. Le test de file SQL ne prouve pas le fencing destination.', '05-revue-integration.html', '08-preuves-risques'),
 ('06 · EL / CDC', 'STREAM et exactly-once', 'Raw sous WAP, puis ack. Qualification encore ouverte pour première création, réponse perdue, transactions et journal rejouable.', '06-annexe-el-cdc-olake.html', '04-edition-publish-ack'),
 ('07 · Planche OLake', 'Writer et scénarios de panne', 'Le sidecar Java sort de la cible. Writer/publisher Rust ; inclure inconnue de commit, zombie, schéma concurrent et restauration derrière ack.', '07-planche-olake-classes-flux.html', '07-migration-decisions'),
 ('08–10 · Étude reprise', 'Frontières et portée des preuves', 'Worker sans table.modify, historique des publications approuvées, preuves post-audit liées, purge hors rollback et lecture par familles de contrats.', '08-plateforme-rust-sans-jvm.html', '05-securite-frontieres'),
 ('DESIGN · Prototype', 'Garanties annoncées', 'Le texte est réécrit autour du comportement réel et de ses quatre contre-exemples ; dix tests verts ne qualifient pas la cible.', '../../cleyrop-dm/DESIGN.md', '08-preuves-risques'),
]
