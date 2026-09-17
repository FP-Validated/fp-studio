"""Explicit one-way IMPORT of v0.2 history. Legacy files are never deleted or rewritten.
Usage: python -m coworker.fp.migrate /path/to/session-scratch infographic
"""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path
import time
from .common import ConflictError, checked_path, digest, dumps, loads, valid_name
from .rendering import validate_artifacts
from .store import Store


def import_v02(workspace: str | Path, name: str):
    store=Store(workspace);valid_name(name)
    legacy=checked_path(store.root,f'.fpstudio/{name}/state.json')
    if not legacy.is_file():raise ValueError('No v0.2 state file found')
    current=loads(legacy.read_text())
    states=[]
    hist=checked_path(store.root,f'.fpstudio/{name}/history')
    if hist.exists():
        for child in sorted(hist.iterdir()):
            state=checked_path(store.root,str((child/'state.json').relative_to(store.root)))
            if state.is_file():states.append((loads(state.read_text()),child/'render.svg',child/'render.png'))
    states.append((current,checked_path(store.root,f'fp/{name}.svg'),checked_path(store.root,f'fp/{name}.png')))
    prepared=[];seen=set();total=0
    for state,svgfile,pngfile in states:
        rev=state.get('revision')
        if type(rev) is not int or rev<1 or rev in seen:raise ValueError('Invalid or duplicate legacy revision')
        seen.add(rev)
        for file in (svgfile,pngfile):checked_path(store.root,str(file.relative_to(store.root)))
        result={'audit':state.get('audit',{}),'frame':state.get('frame',{}),
                'svg':svgfile.read_text('utf-8'),'png_base64':base64.b64encode(pngfile.read_bytes()).decode()}
        svg,png=validate_artifacts(result);raw=dumps(state['input'])
        receipt={'compiler':state.get('compiler'),'legacy_runtime_unknown':True,
                 'renderer_fingerprint':digest(b'unknown-v02-render-environment'),
                 'audit':state['audit'],'frame':state['frame'],
                 'source_sha256':digest(raw.encode()),'svg_sha256':digest(svg),'png_sha256':digest(png),'status':'draft'}
        prepared.append((name,rev,state.get('updated_at',time.time()),raw,svg,png,dumps(receipt),0,None))
        total+=len(svg)+len(png)+len(raw.encode())
    if total>512*1024*1024:raise ValueError('Legacy history exceeds import budget')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if store.current_revision(name,db):raise ConflictError('Destination already has revisions; no import performed')
        db.executemany('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?,?)',prepared)
        db.execute('INSERT INTO heads VALUES (?,?)',(name,current['revision']))
    # Canonical rows are now durable; the cache is byte-identical to the old current output.
    store.materialize(name)
    return {'name':name,'imported_revisions':len(prepared),'current':current['revision'],'legacy_files_preserved':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('name',default='infographic',nargs='?')
    a=p.parse_args();print(json.dumps(import_v02(a.workspace,a.name),indent=2))
