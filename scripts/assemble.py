#!/usr/bin/env python3
"""Assemble an additive fork in a NEW directory. Never delete an existing checkout."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/'UPSTREAMS.lock.json').read_text())

def run(*args,cwd=None):
    subprocess.run(list(args),cwd=cwd,check=True)

def clone_exact(repository,commit,dest,local=None):
    dest=Path(dest)
    if dest.exists():
        raise FileExistsError(f'Refusing to overwrite existing directory: {dest}')
    run('git','-c','core.hooksPath=/dev/null','clone','--no-checkout',str(Path(local).resolve()) if local else repository,str(dest))
    run('git','-c','core.hooksPath=/dev/null','-c','core.autocrlf=false','checkout','--detach',commit,cwd=dest)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=dest,text=True).strip()
    if actual!=commit:
        raise RuntimeError('Pinned commit mismatch')

def copy_overlay(src,dest):
    for file in src.rglob('*'):
        if not file.is_file() or any(p in {'__pycache__','.pytest_cache','node_modules'} for p in file.parts) or file.suffix=='.pyc':
            continue
        if file.is_symlink():
            raise ValueError('Overlay symlinks are refused')
        target=dest/file.relative_to(src)
        if target.exists():
            raise FileExistsError(f'Overlay would overwrite upstream: {target}')
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(file,target)

def main():
    p=argparse.ArgumentParser();p.add_argument('--dest',default=str(ROOT/'build/fp-studio'))
    p.add_argument('--openworker-source');p.add_argument('--fp-kit-source');p.add_argument('--skip-install',action='store_true')
    ns=p.parse_args();dest=Path(ns.dest).expanduser().resolve()
    if dest.exists():
        raise SystemExit('Destination already exists. Choose a NEW directory; no files were deleted.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.fp-assemble-',dir=dest.parent))
    try:
        work=stage/'checkout'
        clone_exact(LOCK['openworker']['repository'],LOCK['openworker']['commit'],work,ns.openworker_source)
        kit=work/'vendor/fp-kit';kit.parent.mkdir(exist_ok=True)
        clone_exact(LOCK['fp-kit']['repository'],LOCK['fp-kit']['commit'],kit,ns.fp_kit_source)
        copy_overlay(ROOT/'overlay',work)
        run(sys.executable,str(ROOT/'scripts/patch_openworker.py'),str(work))
        # Preserve documentation, validation scripts and the exact upstream lock in the fork.
        meta=work/'fp-studio';meta.mkdir()
        for name in ('README.ko.md','UPSTREAMS.lock.json','THIRD_PARTY_NOTICES.md'):
            shutil.copy2(ROOT/name,meta/name)
        shutil.copytree(ROOT/'scripts',meta/'scripts',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copytree(ROOT/'docs',meta/'docs')
        run(sys.executable,str(ROOT/'scripts/check_upstream_ui.py'),str(work))
        if not ns.skip_install:
            run('npm','ci' if (kit/'package-lock.json').is_file() else 'install',cwd=kit)
            run('npm','test',cwd=kit)
            run('node','dist/src/cli.js','tokens','--format','md','--out','docs/DESIGN-LANGUAGE.md',cwd=kit)
            rt=work/'fp_runtime'
            run('npm','ci' if (rt/'package-lock.json').is_file() else 'install',cwd=rt)
            run('npm','test',cwd=rt)
        os.replace(work,dest)
        print(dest)
        print('Assembled exact OpenWorker source with additive FP capabilities. This is not a signed DMG.')
    finally:
        # Only this invocation's private staging directory is removed.
        shutil.rmtree(stage)
if __name__=='__main__':main()
