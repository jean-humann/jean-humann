#!/usr/bin/env python3
"""Read local sources and inventory component roots and declared interfaces.

This extracts declarations, not an active deployment or a complete resolved URL map.
No private source code, environment value or secret is copied into the output.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
EXCLUDE = ('/tests/','/test/','/src/test/','/node_modules/','/.venv/','/build/',
           '/dist/','/.next/','/alembic/','/migrations/','/generated/')


def git(root, *args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def file_list(root):
    result=subprocess.run(['rg','--files','--hidden','-g','!.git','-g','!node_modules',
                           '-g','!.venv','-g','!build','-g','!dist','-g','!.next'],
                          cwd=root,capture_output=True,text=True,check=True)
    return sorted(result.stdout.splitlines())


def loc(text, at):
    return text.count('\n',0,at)+1


def constant(node):
    return node.value if isinstance(node,ast.Constant) and isinstance(node.value,str) else None


def declarations(root, paths):
    found=[]
    for name in paths:
        if not name.startswith(('services/','packages/proto/')) or any(p in '/'+name for p in EXCLUDE):
            continue
        file=root/name
        if file.suffix not in ('.py','.kt','.proto','.tsx','.ts'):
            continue
        text=file.read_text(errors='replace')
        component='/'.join(file.relative_to(root).parts[:2])
        if file.suffix=='.py':
            try:
                tree=ast.parse(text)
            except SyntaxError:
                continue
            for item in ast.walk(tree):
                if not isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    continue
                for deco in item.decorator_list:
                    if not isinstance(deco,ast.Call) or not isinstance(deco.func,ast.Attribute):
                        continue
                    method=deco.func.attr
                    if method in ('get','post','put','patch','delete','head','options','websocket') and deco.args:
                        route=constant(deco.args[0])
                        if route is None:
                            continue
                        found.append(dict(component=component,kind='HTTP/WebSocket declaration',method=method.upper(),
                                          path=route,symbol=item.name,source=name,line=deco.lineno))
                    elif method in ('tool','resource','prompt'):
                        found.append(dict(component=component,kind='MCP declaration',method=method,
                                          path=constant(deco.args[0]) if deco.args else '',symbol=item.name,source=name,line=deco.lineno))
        elif file.suffix=='.kt':
            for match in re.finditer(r'@(Get|Post|Put|Patch|Delete|Request|Message)Mapping\s*(?:\((.{0,1500}?)\))?',text,re.S):
                typ=match.group(1)
                args=match.group(2) or ''
                route=re.search(r'"([^"\n]*)"',args)
                # Retain RequestMapping as a prefix/method declaration, not an independent endpoint.
                nxt=re.search(r'\bfun\s+(\w+)',text[match.end():match.end()+2500])
                found.append(dict(component=component,kind='Spring mapping' if typ!='Request' else 'Spring prefix/mapping',
                                  method=typ.upper(),path=route.group(1) if route else '',
                                  symbol=nxt.group(1) if nxt else '',source=name,line=loc(text,match.start())))
        elif file.suffix=='.proto':
            for match in re.finditer(r'\brpc\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)',text):
                found.append(dict(component=component,kind='Protobuf RPC declaration',method='RPC',path='',
                                  symbol=match.group(1),source=name,line=loc(text,match.start())))
        elif file.name in ('page.tsx','page.ts','route.ts') and '/app/' in name:
            found.append(dict(component=component,kind='Next.js file route',method='PAGE' if file.stem=='page' else 'ROUTE',
                              path=name.split('/app/',1)[1].rsplit('/',1)[0],symbol=file.stem,source=name,line=1))
    for i,item in enumerate(found,1):
        item['id']=f'DECL-{i:04}'
    return found


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('monorepo','icegres','eidos','reference'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    roots=vars(args)
    source_info={}
    for key,root in roots.items():
        source_info[key]={'head':git(root,'rev-parse','HEAD'),
                          'dirty':bool(git(root,'status','--porcelain')),
                          'observation':'working tree read-only; HEAD does not include uncommitted changes'}
    repo=args.monorepo
    paths=file_list(repo)
    planner=json.loads((repo/'ci/components.json').read_text())['components']
    components=[]
    for folder in ('services','packages','charts','hub','images'):
        for item in sorted((repo/folder).iterdir()):
            if not item.is_dir() or item.name.startswith('.'):
                continue
            prefix=f'{folder}/{item.name}'
            owned=[p for p in paths if p.startswith(prefix+'/')]
            registrations=[{'id':k,'adapter':v.get('adapter'),'runtimes':v.get('runtimes',[]),
                            'dependencies':v.get('dependencies',{}),'root':v.get('root')}
                           for k,v in planner.items() if v.get('root')==prefix or str(v.get('root','')).startswith(prefix+'/')]
            metadata=[p for p in owned if Path(p).name in ('AGENTS.md','README.md','Chart.yaml','pyproject.toml','build.gradle.kts','package.json','Dockerfile')]
            components.append({'id':item.name,'root':prefix,'category':folder,'file_count':len(owned),
                               'planner':registrations,'entry_files':metadata[:35]})
    apis=declarations(repo,paths)
    for c in components:
        c['declaration_count']=sum(x['component']==c['root'] for x in apis)
    data={'schema_version':1,'date':'2026-10-02','source_repositories':source_info,'components':components,
          'declarations':apis,
          'limits':['Static declarations do not establish deployed endpoints or runtime authorization.',
                    'Router inclusion prefixes, gateway rewrites and feature flags are not resolved by this extractor.',
                    'Dynamic registration, Vite routes and unannotated handlers require the manual service review.',
                    'No service business behavior is inferred solely from a route name.']}
    (HERE/'inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    import csv
    with (HERE/'interfaces.csv').open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(apis[0]))
        writer.writeheader();writer.writerows(apis)
    print(json.dumps({'components':len(components),'services':sum(c['category']=='services' for c in components),
                      'declared_interfaces':len(apis),'source_heads':source_info},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
