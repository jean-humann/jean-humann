#!/usr/bin/env python3
"""Validate dossier coverage and source references, then check/export its HTML.

No service runtime is exercised by this documentary validation.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote,urlsplit

HERE=Path(__file__).resolve().parent


class HTML(HTMLParser):
    def __init__(self,path):
        super().__init__()
        self.ids=[];self.links=[];self.assets=[];self.text=[]
        self.feed(path.read_text())

    def handle_starttag(self,tag,attributes):
        a=dict(attributes)
        if a.get('id'):
            self.ids.append(a['id'])
        if tag=='a' and a.get('href'):
            self.links.append(a['href'])
        if tag in ('script','img','iframe','source','video','audio') and a.get('src'):
            self.assets.append(a['src'])
        if tag=='link' and a.get('href'):
            self.assets.append(a['href'])

    def handle_data(self,data):
        self.text.append(data)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('monorepo','icegres','eidos','reference'):
        ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--chrome')
    ap.add_argument('--browser',action='store_true')
    ap.add_argument('--export-pdf',action='store_true')
    ap.add_argument('--screenshots',type=Path)
    args=ap.parse_args()
    roots={k:getattr(args,k) for k in ('monorepo','icegres','eidos','reference')}
    roots['study']=HERE.parents[2]
    errors=[]
    report={'schema_version':1,'date':'2026-10-02','scope':'Documentation, coverage and source references only. No production qualification.',
            'preflight':{'demo':'passed before edits','pytest':'10 passed in 0.88s before edits'},
            'source_references':{},'pages':[],'pdfs':[],'errors':errors}
    sources=json.loads((HERE/'evidence-index.json').read_text())
    for key,ref in sources.items():
        source=roots.get(ref['repo'])
        if source is None:
            errors.append(f'Unknown repository {ref["repo"]}: {ref["path"]}')
            continue
        path=source/ref['path']
        if not path.exists():
            errors.append(f'Missing source: {ref["repo"]}/{ref["path"]}')
            continue
        if path.is_dir():
            report['source_references'][key]={'kind':'directory','repo':ref['repo'],'path':ref['path']}
            continue
        lines=len(path.read_text(errors='replace').splitlines())
        if not isinstance(ref['line'],int) or not 1<=ref['line']<=max(1,lines):
            errors.append(f'Invalid line {ref["line"]}: {ref["path"]} ({lines} lines)')
        report['source_references'][key]={'repo':ref['repo'],'path':ref['path'],'line':ref['line'],
                                          'sha256':digest(path),'file_lines':lines}
    coverage=json.loads((HERE/'coverage.json').read_text())
    assert not coverage['missing_service_roots']
    caps=json.loads((HERE/'capabilities.json').read_text())
    required=('id','title','observed','api','state','target','migration','acceptance','evidence')
    for cap in caps:
        for field in required:
            if not cap.get(field):
                errors.append(f'{cap["id"]}: missing {field}')
    report['service_coverage']=len(coverage['service_roots_reviewed'])
    report['capabilities']=len(caps)
    files=[HERE.parent/'12-dossier-services-fonctionnalites.html',*sorted(HERE.glob('*.html')),*sorted((HERE/'services').glob('*.html'))]
    docs={p:HTML(p) for p in files}
    links=0
    for path,doc in docs.items():
        if len(doc.ids)!=len(set(doc.ids)):
            duplicates=[k for k,v in Counter(doc.ids).items() if v>1]
            errors.append(f'{path.name}: duplicate IDs {duplicates[:10]}')
        for u in doc.assets:
            if urlsplit(u).scheme in ('http','https'):
                errors.append(f'{path.name}: external asset {u}')
        if re.search(r'@import|url\([\s\"\x27]*https?://',path.read_text()):
            errors.append(f'{path.name}: external CSS asset')
        for href in doc.links:
            u=urlsplit(href)
            if u.scheme or u.netloc:
                continue
            target=(path.parent/unquote(u.path)).resolve() if u.path else path
            if target.suffix=='.pdf' and args.export_pdf:
                continue
            if target==HERE/'validation.json':
                continue
            links+=1
            if not target.exists():
                errors.append(f'{path.name}: missing {href}')
            elif u.fragment and target.suffix=='.html':
                other=docs.get(target) or HTML(target)
                if unquote(u.fragment) not in other.ids:
                    errors.append(f'{path.name}: missing anchor {href}')
        report['pages'].append({'path':str(path.relative_to(HERE.parent)),'sha256':digest(path),'ids':len(doc.ids)})
    report['local_links_checked']=links
    if args.browser or args.export_pdf:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.chrome,headless=True)
            report['browser']=browser.version
            context=browser.new_context(viewport={'width':1440,'height':1050},device_scale_factor=1)
            requests=[]
            context.route(re.compile(r'^https?://'),lambda route:(requests.append(route.request.url),route.abort()))
            page=context.new_page()
            page.on('pageerror',lambda err:errors.append('JavaScript: '+str(err)))
            if args.screenshots:
                args.screenshots.mkdir(parents=True,exist_ok=True)
            selected=['index.html','fonctionnalites.html','architecture-cible.html','icegres-eidos.html','services/iam.html','services/data-collect.html','services/data-model.html','services/app-management.html']
            for rel in selected:
                path=HERE/rel
                page.goto(path.as_uri())
                if path.name=='fonctionnalites.html':
                    page.locator('#scope').select_option('data-model')
                    assert page.locator('[data-search]:visible').count()==coverage['service_capabilities']['data-model']
                    page.locator('#search').fill('zz-no-match-7491')
                    assert page.locator('[data-search]:visible').count()==0
                    page.locator('#clear').click()
                    assert page.locator('[data-search]:visible').count()==len(caps)
                for theme in ('light','dark'):
                    if page.locator('html').get_attribute('data-theme')!=theme:
                        page.locator('#theme').click()
                    if args.screenshots:
                        page.screenshot(path=str(args.screenshots/(path.stem+'-'+theme+'.png')))
                page.set_viewport_size({'width':390,'height':844})
                if page.evaluate('document.documentElement.scrollWidth>innerWidth+1'):
                    errors.append(f'{rel}: mobile page overflow')
                if args.screenshots:
                    page.screenshot(path=str(args.screenshots/(path.stem+'-mobile.png')))
                page.set_viewport_size({'width':1440,'height':1050})
            report['browser_pages_checked']=selected
            page.set_viewport_size({'width':390,'height':844})
            for path in files:
                page.goto(path.as_uri())
                if page.evaluate('document.documentElement.scrollWidth>innerWidth+1'):
                    errors.append(f'{path.name}: mobile page overflow')
            report['mobile_pages_checked']=len(files)
            page.set_viewport_size({'width':1440,'height':1050})
            report['external_requests']=requests
            if requests:
                errors.append('Offline pages attempted a network request')
            if args.export_pdf:
                exports=[(HERE.parent/'12-dossier-services-fonctionnalites.html',HERE/'exports/hemera-v2-dossier-complet.pdf')]
                exports += [(HERE/'services'/(s+'.html'),HERE/'exports'/('service-'+s+'.pdf')) for s in coverage['service_roots_reviewed']]
                exports += [(HERE/(s+'.html'),HERE/'exports'/(s+'.pdf')) for s in ('architecture-cible','icegres-eidos','infrastructure','parcours-recette','reference')]
                for source,dest in exports:
                    page.goto(source.as_uri())
                    page.emulate_media(media='print',color_scheme='light')
                    page.pdf(path=str(dest),print_background=True,prefer_css_page_size=True,display_header_footer=True,
                             header_template='<div style="font-size:8px;color:#58657c;width:100%;padding:0 14mm">Cleyrop · Hemera v2 · Dossier des services et fonctionnalités</div>',
                             footer_template='<div style="font-size:8px;color:#58657c;width:100%;padding:0 14mm;text-align:right"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
                    info=subprocess.run(['pdfinfo',str(dest)],capture_output=True,text=True,check=True).stdout
                    pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
                    report['pdfs'].append({'file':dest.name,'pages':pages,'sha256':digest(dest)})
                    print(f'Exported {dest.name}: {pages} pages',flush=True)
                fulltext=subprocess.run(['pdftotext',str(HERE/'exports/hemera-v2-dossier-complet.pdf'),'-'],capture_output=True,text=True,check=True).stdout
                missing=[c['id'] for c in caps if c['id'] not in fulltext]
                if missing:
                    errors.append('Capabilities missing from PDF text: '+', '.join(missing))
                report['pdf_capability_ids_verified']=len(caps)-len(missing)
            browser.close()
    report['passed']=not errors
    (HERE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'services':report['service_coverage'],'capabilities':len(caps),
                      'sources':len(sources),'pages':len(files),'links':links,'errors':errors[:40]},ensure_ascii=False,indent=2))
    if errors:
        raise SystemExit(1)


if __name__=='__main__':
    main()
