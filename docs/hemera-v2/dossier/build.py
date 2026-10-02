#!/usr/bin/env python3
"""Render the detailed service dossier from reviewed, source-linked JSON records."""
from collections import Counter, defaultdict
import csv
from html import escape
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
DOCS=HERE.parent
DATA=HERE/'research'
CSS='\n'.join((DOCS/'visuels/atlas.css').read_text().splitlines()[:3])+'\n'+(HERE/'style.css').read_text()
JS=(HERE/'reader.js').read_text()
INVENTORY=json.loads((HERE/'inventory.json').read_text())
SOURCES={}


def e(value):
    return escape(str(value),quote=True)


def slug(value):
    return re.sub(r'[^a-z0-9-]+','-',str(value).lower()).strip('-')


def prose(value):
    if value is None:
        return ''
    if isinstance(value,str):
        return ''.join('<p>'+e(p)+'</p>' for p in value.split('\n\n') if p.strip())
    if isinstance(value,list):
        return '<ul class="compact-list">'+''.join('<li>'+item_text(v)+'</li>' for v in value)+'</ul>'
    if isinstance(value,dict):
        return '<dl>'+''.join(f'<dt>{e(k)}</dt><dd>{item_text(v)}</dd>' for k,v in value.items())+'</dl>'
    return '<p>'+e(value)+'</p>'


def item_text(value):
    if isinstance(value,str):
        return e(value)
    if isinstance(value,dict):
        return '; '.join(e(k)+': '+item_text(v) for k,v in value.items())
    if isinstance(value,list):
        return '; '.join(item_text(v) for v in value)
    return e(value)


def normalized_ref(ref):
    if isinstance(ref,str):
        ref={'path':ref,'line':1,'why':''}
    ref=dict(ref)
    path=ref.get('path',ref.get('file',''))
    repo=ref.get('repo','monorepo')
    mappings={
        '/Users/jean/.t3/worktrees/internal/t3code-3008deaa/':'monorepo',
        '/Users/jean/cleyrop/apps/icegres/':'icegres',
        '/Users/jean/cleyrop/apps/eidos/':'eidos',
        '/Users/jean/.t3/references/iceberg-data-platform/':'reference',
        '/Users/jean/.t3/worktrees/hemera-v2/jean-humann/':'study'}
    for prefix,source in mappings.items():
        if path.startswith(prefix):
            path=path[len(prefix):];repo=source
    for prefix in ('icegres/','eidos/','reference/'):
        if path.startswith(prefix) and 'repo' not in ref:
            path=path[len(prefix):];repo=prefix[:-1]
    if path.startswith(('docs/hemera-v2/','cleyrop-dm/')) or path=='HANDOVER.md':
        repo='study'
    line=ref.get('line',1)
    if isinstance(line,str):
        match=re.search(r'\d+',line);line=int(match.group()) if match else 1
    return {'repo':repo,'path':path,'line':line,'why':ref.get('why',ref.get('note',''))}


def evidence(refs, base=''):
    if not refs:
        return ''
    items=[]
    for raw in refs:
        ref=normalized_ref(raw)
        key=hashlib.sha256(f'{ref["repo"]}:{ref["path"]}:{ref["line"]}'.encode()).hexdigest()[:12]
        if key not in SOURCES:
            SOURCES[key]=dict(ref,claims=[])
        if ref['why'] and ref['why'] not in SOURCES[key]['claims']:
            SOURCES[key]['claims'].append(ref['why'])
        items.append(f'<p><a class="source-path" href="{base}evidence.html#src-{key}">{e(ref["repo"])} · {e(ref["path"])}:{e(ref["line"])}</a> {e(ref["why"])}</p>')
    return '<div class="evidence"><strong>Références de l’analyse</strong>'+''.join(items)+'</div>'


def table(headers,rows,cls=''):
    return '<div class="table-wrap"><table'+(' class="'+cls+'"' if cls else '')+'><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+item_text(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def badge(text,kind='observed'):
    return f'<span class="badge {kind}">{e(text)}</span>'


def capability(s,c,base=''):
    cid=slug(s['id']+'-'+c['id'])
    fields=[('Comportement observé','observed'),('Utilisateurs et rôles','actors'),
            ('Interfaces dans le code','api'),('Données et états','state'),('Dépendances et échanges','dependencies')]
    current=''.join(f'<div class="label">{label}</div>{prose(c.get(key))}' for label,key in fields if c.get(key))
    target='<div class="proposal"><div class="label">Comportement cible proposé</div>'+prose(c.get('target'))+'<div class="label">Migration de cette capacité</div>'+prose(c.get('migration'))+'</div>'
    acceptance='<div class="acceptance"><div class="label">Critère d’acceptation à exécuter</div>'+prose(c.get('acceptance'))+'</div>'
    return f'<article class="capability" id="cap-{cid}"><header class="cap-title">{badge(c["id"])}{badge("Cible non qualifiée","proposed")}<h3>{e(c["title"])}</h3></header><div class="cap-body">{current}{target}{acceptance}{evidence(c.get("evidence",[]),base)}</div></article>'


def service(s,base=''):
    header=f'<section class="service" id="svc-{slug(s["id"])}"><div class="service-head"><div><p class="eyebrow">Service actuel · {e(s["id"])}</p><h2>{e(s.get("title",s["id"]))}</h2></div>{badge(str(len(s.get("capabilities",[])))+" capacités analysées")}</div><p class="service-meta">{e(s.get("source_dir",""))} · {e(s.get("stack",""))}</p>{prose(s.get("purpose"))}'
    header+=f'<div class="status-line">{badge("Lecture de code")}{badge("Pas de qualification runtime nouvelle","open")}</div>'
    if s.get('target_domains'):
        header+='<p class="meta">Domaines cible : '+', '.join(e(v) for v in s['target_domains'])+'.</p>'
    intro=''
    for key,label in [('read_scope','Périmètre de lecture'),('entities','Objets et cycle de vie'),('dependencies','Dépendances du service')]:
        if s.get(key):
            intro+='<div class="panel"><h3>'+label+'</h3>'+prose(s[key])+'</div>'
    caps='<h3>Fonctionnalités et compatibilité à préserver</h3>'+''.join(capability(s,c,base) for c in s.get('capabilities',[]))
    annex=''
    if s.get('connector_inventory'):
        annex='<h3>Les 19 types de connecteurs déclarés</h3>'+prose(s.get('connector_inventory_contract'))
        annex+=table(['Type / famille','Comportement observé','Cible et écart','Acceptation'],[[c['type']+' / '+c['family'],c['observed'],c['target_and_gap'],c['acceptance']] for c in s['connector_inventory']])
        annex+=evidence(s.get('connector_inventory_evidence',[]),base)
    if s.get('action_catalog'):
        yes=lambda value:'Oui' if value else 'Non'
        annex+='<h3>Catalogue des actions de notification</h3>'+prose(s.get('action_catalog_note'))
        annex+=table(['Action','Déclarée en protobuf','Création via DTO abonnement','Template email résolu'],[[c['action'],yes(c['declared_in_protobuf']),yes(c['available_in_subscription_create_dto']),yes(c['email_template_resolved'])] for c in s['action_catalog']])
    architecture=''
    for key,label in [('control_plane','Plan de contrôle Rust proposé'),('data_plane','Plan de données proposé'),('rust_core','Découpage du core Rust'),('security','Identité, autorisation et isolation'),('operations','Exploitation et reprise'),('migration_steps','Séquence de migration'),('open_questions','Écarts et décisions encore ouverts')]:
        if s.get(key):
            architecture+='<div class="panel"><h3>'+label+'</h3>'+prose(s[key])+'</div>'
    return header+intro+caps+annex+'<h3>Architecture et exploitation du service cible</h3>'+architecture+evidence(s.get('evidence',[]),base)+'</section>'


def section(sec,base=''):
    ident=slug(sec.get('id',sec.get('title','section')))
    out=f'<section id="section-{ident}"><h3>{e(sec.get("title",ident))}</h3>'
    out+=prose(sec.get('paragraphs',[]))
    if sec.get('diagram'):
        labels=sec['diagram']
        height=90*len(labels)+20
        boxes=[]
        for i,label in enumerate(labels):
            y=10+i*90
            boxes.append(f'<rect x="20" y="{y}" width="660" height="62" rx="9" fill="var(--soft)" stroke="var(--blue)"/><text x="350" y="{y+36}" text-anchor="middle" fill="var(--ink)" font-size="15" font-family="system-ui">{e(label)}</text>')
            if i<len(labels)-1:
                boxes.append(f'<path d="M350 {y+62} v22 m-5 -6 l5 6 5 -6" fill="none" stroke="var(--teal)" stroke-width="2"/>')
        out+=f'<figure class="diagram"><svg viewBox="0 0 700 {height}" role="img" aria-label="{e(sec["title"])}"><title>{e(sec["title"])}</title>'+''.join(boxes)+'</svg><figcaption>Contrat cible proposé. Chaque transition doit être qualifiée.</figcaption></figure>'
    for t in sec.get('tables',[]):
        out+=table(t['headers'],t['rows'])
    for r in sec.get('requirements',[]):
        out+=f'<article class="panel" id="req-{slug(r["id"])}">{badge(r["id"],"proposed")}<h4>{e(r["title"])}</h4>{prose(r.get("contract"))}<div class="label">Acceptation à exécuter</div>{prose(r.get("acceptance"))}</article>'
    if sec.get('code'):
        out+='<pre>'+e(sec['code'])+'</pre>'
    out+=evidence(sec.get('evidence',[]),base)
    return out+'</section>'


def report(r,base=''):
    return f'<section class="chapter" id="mission-{slug(r["mission"])}"><p class="eyebrow">Étude de domaine</p><h2>{e(r.get("title",r["mission"]))}</h2>{prose(r.get("summary"))}'+''.join(section(s,base) for s in r.get('sections',[]))+'</section>'


def shell(title,body,*,base='',book=False,services=()):
    # base points from this HTML to dossier/; study links are one level above dossier/.
    study=base+'../'
    nav=[('index.html','Vue du dossier'),('fonctionnalites.html','Matrice des fonctionnalités'),
         ('architecture-cible.html','Services et contrats cible'),('icegres-eidos.html','Icegres et Eidos'),
         ('infrastructure.html','Infrastructure et packages'),('parcours-recette.html','Parcours et recette'),
         ('reference.html','Comparaison de la référence'),('interfaces.html','Annexe des interfaces'),('evidence.html','Sources et traçabilité')]
    side='<strong>Dossier complet</strong><nav>'+''.join(f'<a href="{base}{url}">{e(label)}</a>' for url,label in nav)+'</nav>'
    if services:
        side+='<strong>Les 22 services</strong><nav>'+''.join(f'<a href="{base}services/{s["id"]}.html">{e(s["id"])}</a>' for s in services)+'</nav>'
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="Dossier détaillé Hemera v2 : services, fonctionnalités, contrats, migration et sources de code."><title>{e(title)} · Hemera v2</title><style>{CSS}</style></head><body><a class="skip" href="#main">Aller au dossier</a><header class="topbar"><a class="brand" href="{base}index.html">CLEYROP / HEMERA V2</a><nav><a href="{study}12-dossier-services-fonctionnalites.html">Dossier intégral</a><a href="{study}11-atlas-visuel.html">Atlas</a><a href="{base}exports/hemera-v2-dossier-complet.pdf">PDF complet</a><button id="theme">Thème sombre</button></nav></header><div class="layout"><aside class="sidebar">{side}</aside><main id="main">{body}</main></div><footer class="foot">2 octobre 2026 · Lecture de code et conception proposée. Les critères d’acceptation du dossier restent à exécuter ; les résultats historiques du banc conservent leur portée limitée.</footer><script>{JS}</script></body></html>'''


def collect():
    research=[json.loads(p.read_text()) for p in sorted(DATA.glob('*.json'))]
    services=[];transverse=[];additional=[]
    for r in research:
        for s in r.get('services',[]):
            s['_mission']=r['mission']
            if s.get('source_dir','').startswith('services/'):
                services.append(s)
            else:
                additional.append(s)
        if r.get('sections'):
            transverse.append(r)
    order=['iam','keycloak','whitelister','data-collect','files','data-model','data-dev',
           'process-data','data-serve','app-management','devspace-agent','ai-gen-proxy',
           'ai-gen-assistant','mcp-server-dataset','mcp-server-corpus','mcp-server-internet',
           'datasphere-cleyrop','datasphere-front','cleyrop-front-end','business-front-end',
           'notification-center','migration-orchestrator']
    services.sort(key=lambda s:order.index(s['id']) if s['id'] in order else len(order))
    return research,services,additional,transverse


def main():
    research,services,additional,transverse=collect()
    expected={c['id'] for c in INVENTORY['components'] if c['category']=='services'}
    found=[s['id'] for s in services]
    assert set(found)==expected, f'Missing service reviews: {sorted(expected-set(found))}; unexpected: {sorted(set(found)-expected)}'
    assert len(found)==len(set(found)), 'Duplicate service review'
    caps=[dict(c,service=s['id'],anchor='cap-'+slug(s['id']+'-'+c['id'])) for s in services for c in s.get('capabilities',[])]
    assert len({c['id'] for c in caps})==len(caps), 'Capability IDs must be unique across services'
    (HERE/'services').mkdir(exist_ok=True)
    for s in services:
        download=f'<div class="actions"><a href="../exports/service-{s["id"]}.pdf">PDF de ce service</a><a href="../fonctionnalites.html">Matrice des capacités</a></div>'
        (HERE/'services'/(s['id']+'.html')).write_text(shell(s.get('title',s['id']),download+service(s,'../'),base='../',services=services))
    # Missions are grouped by subject. All are also included in the integral document.
    groups={
      'architecture-cible':('Services et contrats de la cible Rust',('14','15','16','17')),
      'icegres-eidos':('Intégration détaillée d’Icegres et d’Eidos',('12','13')),
      'infrastructure':('Infrastructure, packages et exploitation',('10','11','18')),
      'parcours-recette':('Parcours utilisateurs et recette',('19',)),
      'reference':('Comparaison avec iceberg-data-platform',('20',))}
    for filename,(title,prefixes) in groups.items():
        selected=[r for r in transverse if any(str(r['mission']).startswith(p) for p in prefixes)]
        body='<h1>'+e(title)+'</h1>'+''.join(report(r) for r in selected)
        if filename=='infrastructure':
            body+=''.join(service(s) for s in additional if not s.get('source_dir','').startswith(('icegres','eidos')))
        (HERE/(filename+'.html')).write_text(shell(title,body,services=services))
    metrics=f'<div class="metrics"><div class="metric"><strong>{len(services)}</strong><span>services du monorepo examinés</span></div><div class="metric"><strong>{len(caps)}</strong><span>fiches de capacités, avec cible et acceptation</span></div><div class="metric"><strong>{len(INVENTORY["components"])}</strong><span>dossiers recensés, services et support</span></div><div class="metric"><strong>{len(INVENTORY["declarations"])}</strong><span>déclarations d’interfaces indexées</span></div></div>'
    scope_note='<div class="notice">Le recensement porte sur les arbres locaux indiqués dans les sources. Une capacité décrite dans le code n’est pas une preuve de déploiement ou de fonctionnement. Les propositions cible et leurs critères d’acceptation ne sont pas annoncés comme livrés. Les déclarations d’interfaces comprennent des préfixes et registrations partielles ; elles ne forment pas un inventaire de routes actives.</div>'
    cards=''.join(f'<a class="card" href="services/{s["id"]}.html"><small>{e(s["stack"])}</small><h2>{e(s["id"])}</h2><p>{e(s["purpose"])}</p><p>{len(s["capabilities"])} capacités détaillées · {e(", ".join(s.get("target_domains",[])))}</p></a>' for s in services)
    intro='<p class="eyebrow">Dossier de conception fonctionnelle et technique</p><h1>Services, fonctionnalités et trajectoire.</h1><p class="lead">Le dossier décrit les comportements actuels, les données et interfaces, le découpage cible en Rust, la migration et les preuves attendues. Il complète les planches d’architecture par des fiches exploitables pour le développement.</p>'
    actions='<div class="actions"><a href="exports/hemera-v2-dossier-complet.pdf">PDF intégral</a><a href="../12-dossier-services-fonctionnalites.html">Lire tout le dossier en HTML</a><a href="fonctionnalites.csv">Matrice des capacités en CSV</a><a href="interfaces.csv">Déclarations d’interfaces en CSV</a></div>'
    index=intro+metrics+actions+scope_note+'<h2>Fiches détaillées des services</h2><div class="cards">'+cards+'</div>'
    index+='<h2>Chapitres transverses</h2><div class="cards">'+''.join(f'<a class="card" href="{f}.html"><h2>{e(t)}</h2><p>Contrats, dépendances, choix de conception et scénarios d’acceptation.</p></a>' for f,(t,_) in groups.items())+'</div>'
    (HERE/'index.html').write_text(shell('Dossier des services et fonctionnalités',index,services=services))
    # Searchable capability matrix, with full text preserved in service pages.
    choices=''.join(f'<option value="{s["id"]}">{e(s["id"])}</option>' for s in services)
    filters=f'<div class="filters"><div><label for="search">Rechercher une fonctionnalité</label><input id="search" type="search" placeholder="Ex. SharePoint, lineage, publication, SMTP"></div><div><label for="scope">Service</label><select id="scope"><option value="">Tous les services</option>{choices}</select></div><button id="clear">Réinitialiser</button><span class="filter-count" id="filter-count" aria-live="polite"></span></div>'
    rows=''
    for c in caps:
        search=' '.join(str(c.get(k,'')) for k in ('id','title','observed','target','service','api'))
        rows+=f'<tr data-search="{e(search)}" data-scope="{c["service"]}"><td><a href="services/{c["service"]}.html#{c["anchor"]}">{e(c["id"])} · {e(c["title"])}</a><p class="meta">{e(c["service"])}</p></td><td>{item_text(c.get("observed",""))}</td><td>{item_text(c.get("target",""))}</td><td>{item_text(c.get("acceptance",""))}</td></tr>'
    matrix='<h1>Matrice des fonctionnalités</h1>'+metrics+filters+'<div class="table-wrap"><table><thead><tr><th>Capacité et fiche</th><th>Comportement actuel</th><th>Cible proposée</th><th>Acceptation à exécuter</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    (HERE/'fonctionnalites.html').write_text(shell('Matrice des fonctionnalités',matrix,services=services))
    with (HERE/'fonctionnalites.csv').open('w',newline='') as out:
        fields=['service','id','title','observed','actors','api','state','dependencies','target','migration','acceptance']
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        writer.writerows({k:json.dumps(c.get(k,''),ensure_ascii=False) if not isinstance(c.get(k,''),str) else c.get(k,'') for k in fields} for c in caps)
    (HERE/'capabilities.json').write_text(json.dumps(caps,ensure_ascii=False,indent=2)+'\n')
    # The declaration annex is explicitly not a resolved runtime API inventory.
    rows=''
    for d in INVENTORY['declarations']:
        scope=d['component'].split('/')[-1]
        rows+=f'<tr data-search="{e(" ".join(str(v) for v in d.values()))}" data-scope="{scope}"><td>{e(d["id"])}<br>{e(d["component"])}</td><td>{e(d["kind"])}<br><code>{e(d["method"])} {e(d["path"])}</code><br>{e(d["symbol"])}</td><td class="source-path">{e(d["source"])}:{d["line"]}</td></tr>'
    interfaces='<h1>Déclarations d’interfaces</h1>'+scope_note+filters+'<div class="table-wrap"><table><thead><tr><th>Composant</th><th>Déclaration statique</th><th>Fichier et ligne</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    (HERE/'interfaces.html').write_text(shell('Annexe des interfaces déclarées',interfaces,services=services))
    # Integral edition: all current services plus all reviewed transverse domains.
    toc='<section class="book-toc"><h2>Sommaire du dossier</h2><ol>'+''.join(f'<li><a href="#svc-{slug(s["id"])}">{e(s["id"])} : {e(s.get("title",""))}</a></li>' for s in services)+''.join(f'<li><a href="#mission-{slug(r["mission"])}">{e(r.get("title",r["mission"]))}</a></li>' for r in transverse)+'</ol></section>'
    cover='<section class="print-cover"><p class="eyebrow">Cleyrop · Hemera v2 · 2 octobre 2026</p><h1>Dossier des services<br>et des fonctionnalités</h1><p class="lead">Existant, cible Rust sans JVM, intégration Icegres/Eidos, contrats, migration et recette.</p>'+metrics+scope_note+'</section>'
    mapping=table(['Service actuel','Capacités détaillées','Domaines cible proposés'],[[s['id'],len(s['capabilities']),', '.join(s.get('target_domains',[]))] for s in services])
    prelude=''.join(report(r,'dossier/') for r in transverse if str(r['mission']).startswith('00'))
    remainder=''.join(report(r,'dossier/') for r in transverse if not str(r['mission']).startswith('00'))
    book=cover+'<div class="book-title">'+intro+metrics+'</div>'+scope_note+toc+prelude+'<section class="chapter"><h2>Correspondance des responsabilités</h2>'+mapping+'</section>'+''.join(service(s,'dossier/') for s in services)+''.join(service(s,'dossier/') for s in additional)+remainder
    book+='<section class="chapter"><h2>Annexes de navigation et de preuve</h2><p>Les fichiers complémentaires conservent la matrice machine, les déclarations d’interfaces et les preuves de lecture.</p><ul><li><a href="dossier/fonctionnalites.csv">Matrice des fonctionnalités en CSV</a></li><li><a href="dossier/interfaces.csv">Déclarations statiques en CSV</a></li><li><a href="dossier/evidence.html">Sources et empreintes des fichiers consultés</a></li><li><a href="dossier/coverage.json">Couverture des services et composants</a></li></ul></section>'
    (DOCS/'12-dossier-services-fonctionnalites.html').write_text(shell('Dossier intégral des services et fonctionnalités',book,base='dossier/',book=True,services=services))
    # Source registry populated during rendering; validation adds content hashes separately.
    source_body='<h1>Sources et traçabilité</h1><p class="lead">Chaque référence localise le comportement décrit dans l’arbre de travail inspecté. Le dépôt et l’empreinte de fichier distinguent le HEAD des modifications locales d’Icegres et d’Eidos.</p>'+table(['Dépôt','HEAD inspecté','Arbre modifié'],[[k,v['head'],'Oui' if v['dirty'] else 'Non'] for k,v in INVENTORY['source_repositories'].items()])+'<div class="source-index">'
    for key,ref in sorted(SOURCES.items(),key=lambda kv:(kv[1]['repo'],kv[1]['path'],kv[1]['line'])):
        source_body+=f'<article id="src-{key}"><h3>{e(ref["repo"])} · <span class="source-path">{e(ref["path"])}:{ref["line"]}</span></h3>{prose(ref["claims"])}</article>'
    source_body+='</div>'
    (HERE/'evidence.html').write_text(shell('Sources du dossier',source_body,services=services))
    (HERE/'evidence-index.json').write_text(json.dumps(SOURCES,ensure_ascii=False,indent=2)+'\n')
    coverage={'schema_version':1,'date':'2026-10-02','service_roots_expected':sorted(expected),
              'service_roots_reviewed':found,'missing_service_roots':sorted(expected-set(found)),
              'service_capabilities':{s['id']:len(s.get('capabilities',[])) for s in services},
              'capability_count':len(caps),'source_references':len(SOURCES),'transverse_missions':[r['mission'] for r in transverse],
              'support_components':[c['root'] for c in INVENTORY['components'] if c['category']!='services'],
              'scope':'Functional groups and code declarations; not a certification of every execution path or deployed configuration.'}
    (HERE/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(coverage,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
