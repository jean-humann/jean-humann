#!/usr/bin/env python3
"""Build standalone French HTML and SVG files using only the Python standard library."""
from html import escape
from pathlib import Path
import json
import re
import textwrap

from content import ERRATA, PAGES

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parent / '11-atlas-visuel.html'
CSS = (HERE / 'atlas.css').read_text()
SVG_CSS = (HERE / 'diagram.css').read_text()
JS = (HERE / 'atlas.js').read_text()
TOKENS = '\n'.join(CSS.splitlines()[:3])


def e(value):
    return escape(str(value), quote=True)


def svg(p, *, preview=False, export_theme=None):
    slug = p['slug']
    body = p['svg'].replace('ARROW', slug+'-arrow')
    if preview or export_theme:
        body = re.sub(r' (?:data-node|tabindex|role|aria-label|aria-pressed)="[^"]*"', '', body)
    extra = 160 if export_theme else 0
    theme = f' data-theme="{export_theme}"' if export_theme else ''
    start = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {p["height"]+extra}"{theme} '
             f'role="{("img" if preview or export_theme else "group")}" aria-labelledby="{slug}-title {slug}-desc">'
             f'<title id="{slug}-title">{e(p["title"])}</title><desc id="{slug}-desc">{e(p["lead"])} {e(p["caption"])}</desc>')
    style = f'<style>{TOKENS if export_theme else ""}\n{SVG_CSS}</style>'
    defs = f'<defs><marker id="{slug}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9 z" style="fill:var(--muted)"/></marker></defs>'
    if export_theme:
        title = f'<text x="24" y="32" class="tag">HEMERA V2 · CLEYROP · 2 OCTOBRE 2026</text><text x="24" y="65" class="node-title" style="font-size:27px">{e(p["title"])}</text>'
        lines = textwrap.wrap(p['lead'], width=136)
        title += ''.join(f'<text x="24" y="{91+i*19}" class="sub">{e(line)}</text>' for i,line in enumerate(lines))
        body = title + f'<g transform="translate(0 125)">{body}</g>'
        body += f'<text x="24" y="{p["height"]+148}" class="small">{e(p["caption"])}</text>'
    return start+style+defs+body+'</svg>'


def buttons(p=None):
    downloads = '<a href="visuels/exports/hemera-v2-synthese.pdf">PDF direction · 3 pages</a><a href="visuels/exports/hemera-v2-atlas-complet.pdf">PDF complet · 16 pages</a>' if p is None else f'<a href="exports/{p["slug"]}.svg" download>SVG clair</a><a href="exports/{p["slug"]}-dark.svg" download>SVG sombre</a><a href="exports/{p["slug"]}.pdf">PDF · 2 pages</a>'
    return f'<div class="tools"><span class="mode-label">Lecture</span><div class="mode" role="group" aria-label="Niveau de lecture"><button data-level-button="summary" aria-pressed="true">Synthèse</button><button data-level-button="technical" aria-pressed="false">Technique</button></div><button id="theme">Thème sombre</button>{downloads}</div>'


def html_doc(title, body, data, *, gallery=False):
    prefix = '' if gallery else '../'
    menu = f'<a href="{prefix}08-plateforme-rust-sans-jvm.html">Étude</a><a href="{prefix}09-decision-el4-wap.html">EL-4</a><a href="{prefix}10-preuves-et-campagnes.html">Preuves</a>'
    logo = '11-atlas-visuel.html' if gallery else '../11-atlas-visuel.html'
    payload = json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="Atlas visuel Hemera v2 : cible Cleyrop Rust sans JVM, éditions gouvernées, Icegres et Eidos."><title>{e(title)} · Hemera v2</title><style>{CSS}\n{SVG_CSS}</style></head>
<body data-level="summary"><a class="skip" href="#main">Aller au contenu</a><header class="topbar"><a class="brand" href="{logo}">CLEYROP / HEMERA V2</a><nav aria-label="Documents de référence">{menu}</nav></header>{body}<footer>Relecture du 2 octobre 2026 · HTML autonome, sans CDN · Décisions, propositions et preuves sont distinguées. Aucune migration de production n’est livrée par cet atlas.</footer><script id="page-data" type="application/json">{payload}</script><script>{JS}</script></body></html>
'''


def render_page(p, i):
    views = ''.join(f'<button data-view="{j}" aria-pressed="{str(j==0).lower()}">{e(v["label"])}</button>' for j,v in enumerate(p['views']))
    bar = f'<div class="viewbar" role="group" aria-label="Parcours du schéma">{views}</div>' if views else ''
    first = p['details'][p['initial']]
    sim = ''
    if p.get('scenarios'):
        options = ''.join(f'<option value="{k}">{e(v)}</option>' for k,v in p['scenario_labels'].items())
        sim = f'''<div class="simulator"><label for="scenario">Scénario</label><select id="scenario">{options}</select><button id="previous-step" aria-label="Étape précédente">←</button><span id="step-count"></span><button id="next-step" aria-label="Étape suivante">→</button><span class="badge">Simulation pédagogique</span></div><div class="state-grid" aria-live="polite"><div><small>Édition publiée</small><strong id="edition-state">E42</strong></div><div><small>Curseur autoritaire</small><strong id="cursor-state">100</strong></div><div><small>Ack source</small><strong id="ack-state">100</strong></div><div><small>État de tentative</small><strong id="run-state">PRÉPARATION</strong></div></div><p id="sim-description" class="sim-description" aria-live="polite"></p>'''
    takeaways = ''.join(f'<article class="takeaway"><div class="number">0{j+1}</div><h3>{e(a)}</h3><p>{e(b)}</p></article>' for j,(a,b) in enumerate(p['takeaways']))
    contracts = ''.join(f'<article><h3>{e(a)}</h3><p>{e(b)}</p></article>' for a,b in p['contracts'])
    # A complete accessible fallback remains available without JavaScript.
    all_details = ''.join(f'<article><h3>{e(d["title"])}</h3><span class="badge">{e(d["state"])}</span><p>{e(d["summary"])}</p><p>{e(d["technical"])}</p><a href="{e(d["proof"])}">Document de référence</a></article>' for d in p['details'].values())
    refs = ''.join(f'<a href="{e(url)}">{e(label)}</a>' for label,url in p['sources'])
    prev = f'<a href="{PAGES[i-1]["slug"]}.html">← {e(PAGES[i-1]["title"])}</a>' if i else '<a href="../11-atlas-visuel.html">← Atlas</a>'
    nxt = f'<a href="{PAGES[i+1]["slug"]}.html">{e(PAGES[i+1]["title"])} →</a>' if i+1<len(PAGES) else '<a href="../11-atlas-visuel.html">Retour à l’atlas →</a>'
    # The second PDF page selects only the technical decision points, keeping the visual page legible.
    print_nodes = list(p['details'].values())[:4]
    print_cards = ''.join(f'<article><h3>{e(d["title"])}</h3><p><strong>{e(d["state"])}</strong> · {e(d["summary"])}</p><p>{e(d["technical"])}</p></article>' for d in print_nodes)
    print_cards += ''.join(f'<article><h3>{e(a)}</h3><p>{e(b)}</p></article>' for a,b in p['contracts'])
    print_refs = ' · '.join(e(label) for label,_ in p['sources'])
    body = f'''<main id="main"><section class="hero"><p class="eyebrow">Atlas {i+1:02d} / 08 · Direction + équipes techniques</p><h1>{e(p['title'])}</h1><p class="lead">{e(p['lead'])}</p>{buttons(p)}</section><div class="workspace"><div class="visual-panel">{bar}<figure class="figure">{svg(p)}</figure><div class="caption" id="caption">{e(p['caption'])}</div>{sim}</div><aside class="detail" aria-label="Détail du bloc sélectionné"><div class="kicker">Sélectionner un bloc du schéma</div><span class="badge" id="detail-state">{e(first['state'])}</span><h2 id="detail-title">{e(first['title'])}</h2><p id="detail-summary">{e(first['summary'])}</p><div class="technical"><h3>Contrat technique</h3><p id="detail-tech">{e(first['technical'])}</p></div><a class="proof" id="detail-proof" href="{e(first['proof'])}">Lire le document de référence →</a></aside></div><div class="legend"><span>Cible proposée</span><span class="is-observed">Base ou observation locale</span><span class="is-gap">Écart / refus</span><span class="is-gate">Qualification ouverte</span></div><section class="takeaways" aria-label="Messages à retenir">{takeaways}</section><section class="contract technical"><h2>Contrats et limites</h2><div class="contract-grid">{contracts}</div><details class="detail-list"><summary>Tous les blocs du schéma, en texte</summary><div class="contract-grid">{all_details}</div></details></section><noscript>Le schéma reste lisible sans JavaScript. Le détail de chaque bloc est accessible ci-dessous.<div>{all_details}</div></noscript><section class="sources"><strong>Références : </strong>{refs}</section><nav class="pager" aria-label="Autres planches">{prev}{nxt}</nav><section class="print-details"><p class="eyebrow">Atlas {i+1:02d} · Annexe technique</p><h2>{e(p['title'])}</h2><p class="print-meta">{e(p['status'])} · 2 octobre 2026 · L’HTML associé contient tous les blocs, les scénarios et les références.</p><div class="print-grid">{print_cards}</div><p class="print-meta">Sources détaillées dans l’HTML : {print_refs}.<br>Les mécanismes proposés ne sont pas des fonctionnalités déjà livrées. {e(p['caption'])}</p></section></main>'''
    return html_doc(p['title'],body,{k:p[k] for k in ('details','initial','views','scenarios') if k in p})


def gallery():
    cards = ''.join(f'<a class="card" href="visuels/{p["slug"]}.html"><div class="thumb">{svg(p,preview=True)}</div><div class="card-copy"><span class="num">PLANCHE {i+1:02d} · {e(p["status"])}</span><h2>{e(p["title"])}</h2><p>{e(p["lead"])}</p></div></a>' for i,p in enumerate(PAGES))
    errata = ''.join(f'<tr><td><a href="{e(original)}">{e(doc)}</a></td><td>{e(topic)}</td><td>{e(fix)} <a href="visuels/{visual}.html">Voir la planche →</a></td></tr>' for doc,topic,fix,original,visual in ERRATA)
    body = f'''<main id="main"><section class="hero"><p class="eyebrow">Atlas de décision · 2 octobre 2026</p><h1>Voir la prochaine<br>plateforme Cleyrop.</h1><p class="lead">Huit planches pour comprendre la cible Rust sans JVM, réutiliser Icegres et Eidos et décider à partir des preuves disponibles.</p>{buttons()}</section><section class="atlas-intro"><div class="atlas-note"><h2>Deux niveaux de lecture</h2><p><strong>Direction :</strong> commencer par la carte, la trajectoire sans JVM et les décisions de migration : planches 01, 02 et 07.</p><p><strong>Équipes techniques :</strong> suivre Icegres/Eidos, la publication, les frontières de sécurité et les preuves : planches 03, 04, 05 et 08. La planche 06 fixe la taxonomie commune.</p><p>Chaque planche fournit un HTML autonome, un SVG éditable clair/sombre et un PDF de deux pages. Les blocs sont sélectionnables ; la planche 04 déroule six scénarios.</p></div><div class="atlas-note"><h2>Statut de l’étude</h2><p>La cible est décidée. Ses frontières restent à implémenter et qualifier.</p><p>Démo et 10 tests du prototype verts. Banc précédent : 33 entrées qui se recoupent ; plusieurs contrats en défaut. Cette relecture n’a pas relancé le banc réel.</p><a href="10-preuves-et-campagnes.html">Consulter les preuves et leurs limites →</a></div></section><section class="cards" aria-label="Les huit planches">{cards}</section><section class="contract" id="relecture"><p class="eyebrow">Relecture complète</p><h2>Ce qui a été corrigé dans l’étude</h2><p>Les documents 08 à 10 et le DESIGN du prototype sont corrigés dans leur corps. Les sept originaux publiés restent conservés ; ce registre indique les règles qui remplacent leurs passages devenus inexacts.</p><div class="table-scroll"><table><thead><tr><th>Document</th><th>Point relu</th><th>Correction actuelle</th></tr></thead><tbody>{errata}</tbody></table></div></section><section class="contract technical"><h2>Traçabilité et reproduction</h2><div class="contract-grid"><article><h3>Corpus relu</h3><p>01–10, DESIGN, HANDOVER, résultats bruts et quatre contre-épreuves. La première étude mobilisait 20 missions par vagues ; cette relecture réutilise trois agents pour l’architecture, les preuves et la cohérence éditoriale.</p><p>Sources locales conservées : Cleyrop ba0f34e, Icegres e0c175f + modifications locales, Eidos c162af2 + modifications locales. Référence externe : 4506d8a. Aucun arbre source local n’a été modifié.</p></article><article><h3>Sources des artefacts</h3><p>Le générateur Python utilise seulement la bibliothèque standard. CSS, JavaScript, SVG et données d’interaction sont embarqués dans chaque HTML. Les PDF sont exportés depuis ces pages.</p><p><a href="visuels/README.md">Reconstruire et vérifier</a> · <a href="visuels/validation.json">Rapport de validation</a> · <a href="visuels/evidence-classification.json">Familles de preuves</a></p></article></div></section><section class="sources"><strong>Lecture de fond : </strong><a href="08-plateforme-rust-sans-jvm.html">Étude consolidée</a><a href="09-decision-el4-wap.html">Décision EL-4</a><a href="10-preuves-et-campagnes.html">Campagnes</a><a href="../../cleyrop-dm/DESIGN.md">DESIGN révisé</a><a href="README.md">Index et originaux</a></section></main>'''
    return html_doc('Atlas visuel',body,{'details':{},'views':[]},gallery=True)


def main():
    exports = HERE / 'exports'
    exports.mkdir(exist_ok=True)
    for i,p in enumerate(PAGES):
        (HERE / (p['slug']+'.html')).write_text(render_page(p,i))
        for theme,suffix in [('light',''),('dark','-dark')]:
            (exports / (p['slug']+suffix+'.svg')).write_text(svg(p,export_theme=theme))
    ATLAS.write_text(gallery())
    print(f'Built {len(PAGES)} standalone pages, {len(PAGES)*2} SVGs and the atlas.')


if __name__ == '__main__':
    main()
