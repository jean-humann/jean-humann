# Contre-épreuves du prototype

Quatre écarts reproduits sur le prototype inchangé le 2 octobre 2026. Les données sont synthétiques et temporaires, sans accès réseau. Un code de sortie 0 signifie que les contre-exemples sont reproduits, pas que les garanties produit passent.

Depuis `cleyrop-dm`, avec le même interpréteur que celui du préflight :

```sh
python experiments/prototype-counteraudit/counteraudit.py --output /tmp/hemera-counteraudit-results.json
```

Le JSON conservé ici indique les versions, le hash du fichier de catalogue et les résultats. Les quatre cas concernent la première création avant veto, la promotion divergente, les audits/fingerprints et l’exécution Python pendant la préparation d’un plan. Les sondes pourront cesser de reproduire les écarts après leur correction.

Voir [les preuves détaillées](../../../docs/hemera-v2/10-preuves-et-campagnes.html#prototype).
