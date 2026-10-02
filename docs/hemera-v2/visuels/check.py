#!/usr/bin/env python3
"""Validate offline navigation, interactive contracts and printable atlas exports.

Requires Playwright in an isolated environment; it is not a product dependency.
Use --chrome for an installed browser, or install Playwright's Chromium.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright
from content import PAGES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class Document(HTMLParser):
    def __init__(self, file):
        super().__init__()
        self.ids = []
        self.links = []
        self.assets = []
        self.feed(file.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag in ('script', 'img', 'iframe', 'source', 'video', 'audio'):
            self.assets.append(attrs.get('src',''))
        if tag == 'link':
            self.assets.append(attrs.get('href',''))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chrome', help='Path to a Chromium or Chrome executable')
    ap.add_argument('--export-pdf', action='store_true')
    ap.add_argument('--screenshots', type=Path, help='Optional directory outside the repository')
    args = ap.parse_args()
    files = [HERE.parent/'11-atlas-visuel.html'] + [HERE/(p['slug']+'.html') for p in PAGES]
    reviewed = [HERE.parent/(x+'.html') for x in ('08-plateforme-rust-sans-jvm','09-decision-el4-wap','10-preuves-et-campagnes')]
    report = dict(schema_version=1, date='2026-10-02', scope='Visual and documentary validation only; no new live platform qualification.',
                  pages=[], pdfs=[], errors=[], static_links=0,
                  prototype_preflight={'demo':'passed before edits','pytest':'10 passed in 1.34s before edits','production_qualification':False},
                  live_campaigns_rerun=False)
    errors = report['errors']
    for file in files+reviewed:
        doc = Document(file)
        if len(doc.ids)!=len(set(doc.ids)):
            errors.append(f'{file.name}: duplicate HTML id')
        for asset in doc.assets:
            if urlsplit(asset).scheme in ('http','https'):
                errors.append(f'{file.name}: external asset {asset}')
        if re.search(r'@import|url\([\s\"\x27]*https?://',file.read_text()):
            errors.append(f'{file.name}: external CSS asset')
        for link in doc.links:
            u=urlsplit(link)
            if u.scheme or u.netloc:
                continue
            target=(file.parent/unquote(u.path)).resolve() if u.path else file
            # PDFs are produced later in this validation run.
            if args.export_pdf and target.suffix=='.pdf' and target.parent==HERE/'exports':
                continue
            if target.name=='validation.json' and target.parent==HERE:
                continue
            report['static_links']+=1
            if not target.exists():
                errors.append(f'{file.name}: missing {link}')
            elif u.fragment and target.suffix=='.html' and unquote(u.fragment) not in Document(target).ids:
                errors.append(f'{file.name}: missing anchor {link}')
    if args.screenshots:
        args.screenshots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.chrome,headless=True)
        report['browser']=browser.version
        context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
        requests=[]
        context.route(re.compile(r'^https?://'),lambda route:(requests.append(route.request.url),route.abort()))
        page=context.new_page()
        page.on('pageerror',lambda err:errors.append('JavaScript: '+str(err)))
        for file in files:
            page.goto(file.as_uri())
            page.locator('[data-level-button="summary"]').click()
            metrics={'file':file.name,'html_sha256':sha(file)}
            if file.parent==HERE:
                data=page.locator('#page-data').text_content()
                data=json.loads(data)
                nodes=page.locator('.figure [data-node]')
                metrics['interactive_nodes']=nodes.count()
                page.locator('[data-level-button="technical"]').click()
                for key,value in data['details'].items():
                    item=page.locator(f'.figure [data-node="{key}"]')
                    item.focus()
                    item.press('Enter')
                    assert page.locator('#detail-title').inner_text()==value['title']
                    assert page.locator('#detail-tech').is_visible()
                    assert item.get_attribute('aria-pressed')=='true'
                for i,v in enumerate(data['views']):
                    page.locator(f'[data-view="{i}"]').click()
                    assert page.locator('#caption').inner_text()==v['caption']
                    if v['nodes']:
                        assert page.locator('.figure .node:not(.dim)').count()==len(v['nodes'])
                if data['views']:
                    page.locator('[data-view="0"]').click()
                metrics['view_filters']=len(data['views'])
                if 'scenarios' in data:
                    metrics['scenarios']={}
                    for key,steps in data['scenarios'].items():
                        page.locator('#scenario').select_option(key)
                        for j,step in enumerate(steps):
                            assert page.locator('#edition-state').inner_text()==step['edition']
                            assert page.locator('#cursor-state').inner_text()==step['cursor']
                            assert page.locator('#ack-state').inner_text()==step['ack']
                            if j+1<len(steps):
                                page.locator('#next-step').click()
                        metrics['scenarios'][key]=dict(steps=len(steps),final=steps[-1]['state'])
                    # Independent contract expectations, not only presentation/data agreement.
                    page.locator('#scenario').select_option('veto')
                    page.locator('#next-step').click()
                    page.locator('#next-step').click()
                    assert page.locator('#edition-state').inner_text()=='E42'
                    assert page.locator('#ack-state').inner_text()=='100'
                    page.locator('#scenario').select_option('normal')
                    for _ in range(3):
                        page.locator('#next-step').click()
                    assert page.locator('#edition-state').inner_text()=='E43'
                    assert page.locator('#cursor-state').inner_text()=='120'
                    assert page.locator('#ack-state').inner_text()=='100'
                    page.locator('#scenario').select_option('normal')
                clipping=page.locator('.figure svg').evaluate('''svg=>{
                  const v=svg.viewBox.baseVal, out=[];
                  for(const t of svg.querySelectorAll('text')){
                    const b=t.getBBox(); if(!t.textContent.trim())continue;
                    if(b.x<0||b.y<0||b.x+b.width>v.width+1||b.y+b.height>v.height+1)out.push('canvas: '+t.textContent);
                    const n=t.closest('.node'), r=n?.querySelector('.node-bg');
                    if(r){const q=r.getBBox();if(b.x<q.x-1||b.x+b.width>q.x+q.width-7||b.y+b.height>q.y+q.height-1)out.push('node: '+t.textContent)}
                  } return out;
                }''')
                errors.extend(f'{file.name}: clipped SVG {c}' for c in clipping)
                page.locator('[data-level-button="summary"]').click()
            for theme in ('light','dark'):
                if page.locator('html').get_attribute('data-theme')!=theme:
                    page.locator('#theme').click()
                if args.screenshots:
                    page.screenshot(path=str(args.screenshots/(file.stem+'-'+theme+'.png')),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            # The diagram scrolls inside its panel; the whole mobile document must not overflow.
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            if overflow:
                errors.append(f'{file.name}: mobile document overflows')
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/(file.stem+'-mobile.png')),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            metrics.update(themes=['light','dark'],mobile_width=390)
            report['pages'].append(metrics)
            if args.export_pdf and file.parent==HERE:
                page.emulate_media(media='print',color_scheme='light')
                # Restore all blocks for static export, including a simulator's highlighted node.
                page.evaluate("document.querySelectorAll('.dim,.selected').forEach(e=>e.classList.remove('dim','selected'))")
                dest=HERE/'exports'/(file.stem+'.pdf')
                page.pdf(path=str(dest),print_background=True,prefer_css_page_size=True)
                info=subprocess.run(['pdfinfo',str(dest)],capture_output=True,text=True,check=True).stdout
                count=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
                report['pdfs'].append({'file':dest.name,'pages':count,'sha256':sha(dest)})
                if count!=2:
                    errors.append(f'{dest.name}: expected 2 pages, got {count}')
                page.emulate_media(media='screen')
        # No-JavaScript users retain the diagram and its full text.
        static=browser.new_context(java_script_enabled=False,viewport={'width':1280,'height':900})
        plain=static.new_page()
        plain.goto((HERE/'04-edition-publish-ack.html').as_uri())
        assert plain.locator('noscript').is_visible()
        assert plain.locator('noscript article').count()==6
        report['no_javascript_fallback']='passed'
        report['external_runtime_requests']=requests
        if requests:
            errors.append('Standalone HTML attempted external network requests')
        browser.close()
    if args.export_pdf:
        full=HERE/'exports'/'hemera-v2-atlas-complet.pdf'
        subprocess.run(['pdfunite',*[str(HERE/'exports'/(p['slug']+'.pdf')) for p in PAGES],str(full)],check=True)
        synth=HERE/'exports'/'hemera-v2-synthese.pdf'
        with TemporaryDirectory(prefix='hemera-atlas-') as tmp:
            selected=[]
            for i in (0,1,6):
                source=HERE/'exports'/(PAGES[i]['slug']+'.pdf')
                pattern=Path(tmp)/f'{i}-%d.pdf'
                subprocess.run(['pdfseparate','-f','1','-l','1',str(source),str(pattern)],check=True)
                selected.append(str(Path(tmp)/f'{i}-1.pdf'))
            subprocess.run(['pdfunite',*selected,str(synth)],check=True)
        for dest,want in ((full,16),(synth,3)):
            info=subprocess.run(['pdfinfo',str(dest)],capture_output=True,text=True,check=True).stdout
            count=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
            report['pdfs'].append({'file':dest.name,'pages':count,'sha256':sha(dest)})
            if count!=want:
                errors.append(f'{dest.name}: expected {want} pages, got {count}')
    else:
        for file in sorted((HERE/'exports').glob('*.pdf')):
            report['pdfs'].append({'file':file.name,'sha256':sha(file)})
    report['passed']=not errors
    (HERE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'pages':len(report['pages']),'pdfs':len(report['pdfs']),'links':report['static_links'],'errors':errors},ensure_ascii=False,indent=2))
    if errors:
        raise SystemExit(1)


if __name__=='__main__':
    main()
