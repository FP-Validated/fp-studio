"""Assembly mechanics: the parts that only exist in this repository.

Product behaviour (render, research, migration, SDK routing, design rules, providers) is
tested by the suites in `overlay/tests`, which run inside an assembled checkout where the
upstream package and the pinned kit are present. Keeping a second copy here is what let
this repository drift from the tree that was actually shipped, so it is not done.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = 'surfaces/gui/src-tauri/icons'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def test_assembly_refuses_existing_destination(tmp_path):
    dest = tmp_path / 'important'
    dest.mkdir()
    sentinel = dest / 'work.txt'
    sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        load('assemble').clone_exact('irrelevant', '0' * 40, dest)
    assert sentinel.read_text() == 'keep'


def test_overlay_cannot_replace_original_file(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.mkdir()
    dst.mkdir()
    (src / 'App.tsx').write_text('new GUI')
    (dst / 'App.tsx').write_text('original GUI')
    with pytest.raises(FileExistsError):
        load('assemble').copy_overlay(src, dst)
    assert (dst / 'App.tsx').read_text() == 'original GUI'


def test_cache_directories_are_not_packaged(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.mkdir()
    dst.mkdir()
    (src / 'tests/.pytest_cache').mkdir(parents=True)
    (src / 'tests/.pytest_cache/state').write_text('cache')
    (src / 'tests/test_real.py').write_text('assert True')
    load('assemble').copy_overlay(src, dst)
    assert (dst / 'tests/test_real.py').exists()
    assert not (dst / 'tests/.pytest_cache').exists()


def test_exact_patcher_refuses_drift(tmp_path):
    file = tmp_path / 'source'
    file.write_text('changed upstream')
    with pytest.raises(RuntimeError):
        load('patch_openworker').replace_once(file, 'expected upstream', 'patch', 'test')
    assert file.read_text() == 'changed upstream'


def test_additive_gui_contract():
    import subprocess
    subprocess.run([sys.executable, str(ROOT / 'scripts/check_overlay.py')], check=True)


def _anchor_fixture(tmp_path, edits, icons):
    """A tree containing exactly the upstream text the declared edits anchor on."""
    grouped: dict[str, list[str]] = {}
    for relative, old, _new, _label in edits:
        grouped.setdefault(relative, []).append(old)
    for relative, anchors in grouped.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(anchors), 'utf-8')
    for icon in icons:
        slot = tmp_path / ICON_DIR / icon.name
        slot.parent.mkdir(parents=True, exist_ok=True)
        slot.write_bytes(b'upstream icon')
    conf = tmp_path / 'surfaces/gui/src-tauri/tauri.conf.json'
    conf.write_text(json.dumps({
        'identifier': 'com.openworker.desktop',
        'productName': 'OpenWorker',
        'version': '0.0.0',
        'bundle': {'resources': {}},
        'plugins': {'updater': {'endpoints': ['https://upstream.example/updates']}},
    }))
    return conf


def _icons():
    return sorted(p for p in (ROOT / 'assets/icons').iterdir()
                  if p.is_file() and p.name != 'MANIFEST.json')


def test_declared_edit_set_applies_once_and_is_recorded(tmp_path):
    """Every hunk in `fp_edits.EDITS` lands, and the manifest records what was applied.

    The manifest is the contract `check_upstream_ui.py` replays against the pinned
    upstream blobs, so an edit that applies without being recorded would make that gate
    pass on an undeclared change.
    """
    patcher = load('patch_openworker')
    edits = load('fp_edits').EDITS
    icons = _icons()
    conf = _anchor_fixture(tmp_path, edits, icons)

    patcher.patch(tmp_path)

    for relative, _old, new, _label in edits:
        assert new in (tmp_path / relative).read_text('utf-8')
    manifest = json.loads((tmp_path / '.fp-patch-manifest.json').read_text())
    assert len(manifest) == len(edits) + len(icons) + 1
    assert [e['label'] for e in manifest[:len(edits)]] == [e[3] for e in edits]
    assert manifest[-1]['label'] == 'Fork bundle identity'

    identity = json.loads(conf.read_text())
    assert identity['identifier'] == 'com.fourpillars.fpstudio'
    assert identity['productName'] == 'FP Studio'
    assert identity['bundle']['resources']['binaries/fp-runtime'] == 'fp-runtime'
    # FP Studio ships no updater: upstream's endpoints must not survive the fork.
    assert identity['plugins']['updater']['endpoints'] == []


def test_patcher_refuses_an_icon_slot_upstream_does_not_have(tmp_path):
    patcher = load('patch_openworker')
    edits = load('fp_edits').EDITS
    icons = _icons()
    _anchor_fixture(tmp_path, edits, icons)
    (tmp_path / ICON_DIR / icons[0].name).unlink()
    with pytest.raises(RuntimeError, match='Icon slot is absent'):
        patcher.patch(tmp_path)


def test_replaced_icons_match_their_recorded_digests():
    recorded = json.loads((ROOT / 'assets/icons/MANIFEST.json').read_text())
    actual = {f'{ICON_DIR}/{p.name}': hashlib.sha256(p.read_bytes()).hexdigest()
              for p in _icons()}
    assert actual == recorded
