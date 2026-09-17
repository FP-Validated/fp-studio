#!/usr/bin/env python3
"""The overlay may ADD capability files; it may not add a second application.

What lands in the existing React tree is enumerated by name, not by pattern: a pure
request-order helper, a locale catalog (data), and tests. A new component, page,
route, canvas, stylesheet or template would need an entry here, and that is the
review that matters — `check_upstream_ui.py` covers edits to upstream files.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
# name -> why it is allowed to exist in the stock GUI tree.
GUI_ADDITIONS = {
    'latestArtifact.ts': 'request-order helper for the stock artifact viewer',
    'latestArtifact.test.ts': 'its test',
    'ko.json': 'Korean locale catalog beside en/zh — data, no UI',
    'Composer.ime.test.tsx': 'IME regression test for the stock composer',
}
for file in (root / 'overlay/surfaces/gui/src').rglob('*'):
    if not file.is_file():
        continue
    if file.name not in GUI_ADDITIONS:
        raise SystemExit('Unexpected GUI overlay: ' + str(file))
assert not (root / 'overlay/apps').exists()
assert not list((root / 'overlay').rglob('*.css'))
assert not list((root / 'overlay').rglob('*.tsx')) or set(
    p.name for p in (root / 'overlay').rglob('*.tsx')
) <= set(GUI_ADDITIONS)
for f in ('fp.py',):
    assert (root / 'overlay/coworker/tools' / f).is_file()
# Subscription sign-in and model discovery are provider plumbing, not new surfaces: each
# module sits in the stock providers package and is reached through the stock descriptor
# registry. Four vendors × (API key | subscription) = the eight login methods FP Studio
# offers; nothing here adds a screen.
for f in (
    'anthropic_auth.py',
    'claude_subscription_provider.py',
    'xai_auth.py',
    'grok_subscription_provider.py',
    'gemini_auth.py',
    'gemini_code_assist_provider.py',
    'discovery.py',
):
    assert (root / 'overlay/coworker/providers' / f).is_file(), f
# The FOUR PILLARS design rules ship as data, enforced by fp_render at runtime: a decision
# card the model reads on every authoring call, plus the verbatim guideline appendix it
# reads only when a frame value is in doubt.
for f in ('fp-design-system', 'fp-design-table', 'fp-design-chart', 'fp-design-flowchart'):
    for part in ('SKILL.md', 'APPENDIX.md'):
        assert (root / 'overlay/coworker/fp/design_skills' / f / part).is_file(), f'{f}/{part}'
assert (root / 'overlay/coworker/fp/design_skills/fp-design-reproduce/SKILL.md').is_file()
assert (root / 'overlay/coworker/fp/design.py').is_file()
# Pointer edits: the write path that changes a stored document without resending it.
assert (root / 'overlay/coworker/fp/patch.py').is_file()
print('overlay-contract: no new application, pages, templates, JSX components or CSS')
