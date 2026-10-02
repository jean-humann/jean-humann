# Atlas visuel Hemera v2

Entrée : [atlas des huit planches](../11-atlas-visuel.html). Chaque HTML est
autonome et fonctionne depuis le disque, sans serveur ni accès réseau. Les
liens vers les sources externes ne sont ouverts qu’à la demande du lecteur.

Les boutons **Synthèse / Technique** et **Thème clair / sombre** restent
disponibles sur chaque page. Les blocs du SVG sont accessibles au clavier
(Tab, puis Entrée ou Espace). La planche 04 contient six simulations
pédagogiques du contrat ; elles ne constituent pas des tests de la plateforme.

Les PDF contiennent une planche visuelle et une annexe technique sélectionnée.
L’HTML fournit le détail complet et les références. Les SVG clair et sombre
conservent des textes éditables et la légende de statut.

- [Synthèse direction, trois pages](exports/hemera-v2-synthese.pdf) : carte,
  trajectoire sans JVM et migration.
- [Atlas complet, seize pages](exports/hemera-v2-atlas-complet.pdf) : les huit
  planches avec leur annexe technique.

## Reconstruire les HTML et SVG

Depuis la racine du dépôt, avec Python 3.10 ou plus récent :

```bash
python docs/hemera-v2/visuels/build.py
```

Le générateur utilise seulement la bibliothèque standard. Modifier
`content.py`, `components.py`, `build.py`, `atlas.css`, `diagram.css` ou
`atlas.js`, puis reconstruire. Ne pas modifier directement les HTML générés.
La classification des preuves vient de `evidence-classification.json` ; les
résultats bruts du banc ne sont pas modifiés.

## Vérifier et exporter les PDF

Playwright est une dépendance de validation documentaire, isolée du produit.
La validation de cette livraison utilise Playwright 1.63.0, Chrome local et
`pdfinfo`, `pdfseparate` et `pdfunite` (Poppler). Installer Chromium avec Playwright si Chrome n’est pas
disponible ; dans ce cas omettre `--chrome`.

```bash
python -m venv /tmp/hemera-atlas-check
/tmp/hemera-atlas-check/bin/python -m pip install playwright==1.63.0
/tmp/hemera-atlas-check/bin/python -m playwright install chromium
/tmp/hemera-atlas-check/bin/python docs/hemera-v2/visuels/check.py \
  --export-pdf --screenshots /tmp/hemera-atlas-previews
```

Sur macOS avec Chrome installé :

```bash
/tmp/hemera-atlas-check/bin/python docs/hemera-v2/visuels/check.py \
  --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --export-pdf --screenshots /tmp/hemera-atlas-previews
```

`check.py` contrôle les liens locaux, ancres, identifiants, absence d’assets
réseau, sélection au clavier, filtres, états des six scénarios, débordements
SVG, thème clair/sombre, largeur mobile et lecture sans JavaScript. Il vérifie
que chaque PDF contient deux pages. Les captures restent hors du dépôt.

Le [rapport JSON](validation.json) consigne ce contrôle documentaire. Il ne
qualifie ni WAP, ni le fencing, ni les mécanismes de production représentés.
Le banc réel précédent n’a pas été relancé pendant cette relecture.
