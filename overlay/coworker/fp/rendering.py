"""Bounded, interruptible renderer process. Only bundled code runs, never model JS."""
from __future__ import annotations
import base64
import contextlib
import fcntl
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from .common import MAX_INPUT, checked_path, dumps, loads

MAX_OUTPUT=80*1024*1024
MAX_PIXELS=16_000_000


def repo_root():
    return Path(__file__).resolve().parents[2]


def runtime_root():
    custom=os.environ.get('FP_STUDIO_RUNTIME_DIR')
    if custom:
        return Path(custom).expanduser().resolve()
    exe=Path(sys.executable).resolve()
    for p in (exe.parent.parent/'fp-runtime',exe.parent/'fp-runtime',repo_root()/'fp_runtime'):
        if (p/'worker.mjs').is_file():
            return p
    raise RuntimeError('FP runtime missing; install a complete FP Studio build')


def kit_root():
    rt=runtime_root()
    bundled=rt/'fp-kit'
    return bundled if bundled.is_dir() else repo_root()/'vendor'/'fp-kit'


class RenderController:
    def __init__(self):
        self.cancelled=threading.Event()
        self._guard=threading.Lock()
        self._child=None

    def interrupt(self):
        self.cancelled.set()
        with self._guard:
            child=self._child
            if child and child.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid,signal.SIGKILL)

    def run(self, value: dict, workspace: Path, *, timeout=45) -> dict:
        self.cancelled.clear()
        raw=dumps({'input':value}).encode('utf-8')
        if len(raw)>MAX_INPUT:
            raise ValueError('FP document exceeds 2 MiB')
        runtime=runtime_root()
        node=os.environ.get('FP_STUDIO_NODE') or str(runtime/'node'/'bin'/'node')
        if not Path(node).is_file():
            node=shutil.which('node') or ''
        if not node:
            raise RuntimeError('Bundled Node is missing')
        cmd=[node,'--max-old-space-size=384',str(runtime/'worker.mjs')]
        # An override is available only for an explicitly opted-in local test process.
        if os.environ.get('FP_STUDIO_TESTING')=='1' and os.environ.get('FP_STUDIO_RENDER_CMD'):
            import shlex
            cmd=shlex.split(os.environ['FP_STUDIO_RENDER_CMD'])
        # Do not forward provider keys, NODE_OPTIONS, NODE_PATH, proxy or injection env.
        env={k:os.environ[k] for k in ('PATH','HOME','LANG','LC_ALL','TMPDIR','SYSTEMROOT') if k in os.environ}
        env.update({'FP_KIT_ROOT':str(kit_root()),'FP_RUNTIME_ROOT':str(runtime)})
        fonts=runtime/'fonts'
        env['FP_FONT_DIR']=str(fonts if fonts.is_dir() else Path(os.environ.get('FP_FONT_DIR','__missing_fonts__')).resolve())
        lock=checked_path(workspace,'.fpstudio/render.lock',create_parent=True)
        start=time.monotonic()
        with lock.open('a+b') as guard, tempfile.TemporaryFile() as inp:
            while True:
                if self.cancelled.is_set():
                    raise InterruptedError('Render cancelled before start')
                try:
                    fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic()-start>timeout:
                        raise TimeoutError('Render queue timeout')
                    time.sleep(.05)
            inp.write(raw); inp.seek(0)
            with subprocess.Popen(cmd,stdin=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  cwd=runtime,env=env,start_new_session=True) as child:
                with self._guard:
                    self._child=child
                chunks={1:bytearray(),2:bytearray()}
                try:
                    with selectors.DefaultSelector() as sel:
                        sel.register(child.stdout,selectors.EVENT_READ,1)
                        sel.register(child.stderr,selectors.EVENT_READ,2)
                        while sel.get_map():
                            if self.cancelled.is_set():
                                raise InterruptedError('Render cancelled')
                            if time.monotonic()-start>timeout:
                                raise TimeoutError('Renderer exceeded time budget')
                            for key,_ in sel.select(.05):
                                b=os.read(key.fileobj.fileno(),65536)
                                if not b:
                                    sel.unregister(key.fileobj);continue
                                target=chunks[key.data];target.extend(b)
                                if len(target)>(MAX_OUTPUT if key.data==1 else 1024*1024):
                                    raise ValueError('Renderer output exceeds limit')
                    child.wait(timeout=max(.01,timeout-(time.monotonic()-start)))
                except BaseException:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child.pid,signal.SIGKILL)
                    child.wait()
                    raise
                finally:
                    with self._guard:
                        self._child=None
                if self.cancelled.is_set():
                    raise InterruptedError('Render cancelled before commit')
                try:
                    result=json.loads(chunks[1])
                except (ValueError,UnicodeError) as e:
                    raise RuntimeError('Renderer returned malformed JSON; no revision committed') from e
                if child.returncode or not isinstance(result,dict) or not result.get('ok'):
                    detail=result.get('error','Unknown render error') if isinstance(result,dict) else 'Invalid output'
                    raise RuntimeError(str(detail)[:1800])
                return result


def validate_artifacts(result: dict):
    if not result.get('audit',{}).get('ok'):
        raise ValueError('Refusing failed or missing compiler audit')
    svg=result.get('svg'); encoded=result.get('png_base64')
    if not isinstance(svg,str) or len(svg.encode('utf-8'))>32*1024*1024 or not isinstance(encoded,str):
        raise ValueError('Missing or oversized SVG/PNG')
    if '<!DOCTYPE' in svg.upper() or '<!ENTITY' in svg.upper():
        raise ValueError('SVG declarations are not supported')
    try:
        root=ET.fromstring(svg)
    except ET.ParseError as e:
        raise ValueError('Malformed SVG') from e
    allowed={'svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon','linearGradient','radialGradient','stop','clipPath','mask','title','desc','use'}
    for el in root.iter():
        tag=el.tag.split('}')[-1]
        if tag not in allowed:
            raise ValueError(f'Unsafe or unsupported outlined SVG element: {tag}')
        for key,v in el.attrib.items():
            attr=key.split('}')[-1].lower()
            if attr.startswith('on') or attr in {'style','base'}:
                raise ValueError('Executable/CSS SVG attribute refused')
            if attr in {'href','src'} and not v.startswith('#'):
                raise ValueError('External SVG reference refused')
            if re_url(v):
                raise ValueError('External paint reference refused')
    if root.tag.split('}')[-1]!='svg':
        raise ValueError('SVG root is missing')
    png=base64.b64decode(encoded,validate=True)
    if len(png)>32*1024*1024 or len(png)<33 or png[:8]!=b'\x89PNG\r\n\x1a\n' or png[12:16]!=b'IHDR':
        raise ValueError('Invalid PNG')
    w,h=struct.unpack('>II',png[16:24])
    frame=result.get('frame',{})
    if not w or not h or w*h>MAX_PIXELS or w!=frame.get('width') or h!=frame.get('height'):
        raise ValueError('PNG/frame dimensions disagree or exceed budget')
    # Walk every chunk and verify CRC plus IEND; header-only test images are not valid PNGs.
    import zlib
    pos=8; ended=False
    while pos<len(png):
        if pos+12>len(png):
            raise ValueError('Truncated PNG chunk')
        n=struct.unpack('>I',png[pos:pos+4])[0]
        end=pos+n+12
        if end>len(png):
            raise ValueError('Truncated PNG payload')
        if zlib.crc32(png[pos+4:end-4])&0xffffffff != struct.unpack('>I',png[end-4:end])[0]:
            raise ValueError('PNG CRC mismatch')
        if png[pos+4:pos+8]==b'IEND':
            if n or end!=len(png):
                raise ValueError('Invalid PNG ending')
            ended=True
        pos=end
    if not ended:
        raise ValueError('PNG has no IEND')
    return svg.encode('utf-8'),png


def re_url(value):
    import re
    return any(not s.strip(' \"\'').startswith('#') for s in re.findall(r'url\((.*?)\)',value,re.I))
