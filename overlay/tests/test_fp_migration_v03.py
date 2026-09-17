import base64
import json
from pathlib import Path
import pytest
from coworker.fp.migrate import import_v02
from coworker.fp.store import Store
from coworker.fp.common import ConflictError
from test_fp_core_v03 import rendered

def test_legacy_import_preserves_exact_bytes(tmp_path):
    result=rendered()
    base=tmp_path/'.fpstudio/infographic';base.mkdir(parents=True)
    state={'revision':1,'updated_at':123,'input':{'title':'Old'},'audit':result['audit'],'frame':result['frame'],'compiler':'old'}
    original=json.dumps(state);(base/'state.json').write_text(original)
    output=tmp_path/'fp';output.mkdir();(output/'infographic.svg').write_text(result['svg'])
    (output/'infographic.png').write_bytes(base64.b64decode(result['png_base64']))
    imported=import_v02(tmp_path,'infographic')
    assert imported['imported_revisions']==1
    assert (base/'state.json').read_text()==original
    assert Store(tmp_path).get('infographic')['svg']==result['svg'].encode()
    with pytest.raises(ConflictError):import_v02(tmp_path,'infographic')
