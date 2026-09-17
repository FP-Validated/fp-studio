"""Real child-process tests, not real compiler tests."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import pytest
from coworker.fp.rendering import RenderController

@pytest.fixture
def runtime(tmp_path,monkeypatch):
    rt=tmp_path/'runtime';rt.mkdir();(rt/'worker.mjs').write_text('// not executed by the test')
    (rt/'fp-kit').mkdir()
    monkeypatch.setenv('FP_STUDIO_RUNTIME_DIR',str(rt));monkeypatch.setenv('FP_STUDIO_TESTING','1')
    return rt

def script(rt,monkeypatch,text):
    file=rt/'mock.py';file.write_text(text)
    import shlex
    monkeypatch.setenv('FP_STUDIO_RENDER_CMD',shlex.join([sys.executable,str(file)]))

def test_child_timeout(runtime,tmp_path,monkeypatch):
    script(runtime,monkeypatch,'import time;time.sleep(20)')
    with pytest.raises(TimeoutError):RenderController().run({},tmp_path,timeout=.15)

def test_child_stop_kills_process(runtime,tmp_path,monkeypatch):
    script(runtime,monkeypatch,'import time;time.sleep(20)')
    controller=RenderController();error=[]
    def task():
        try:controller.run({},tmp_path,timeout=5)
        except BaseException as e:error.append(e)
    thread=threading.Thread(target=task);thread.start()
    for _ in range(100):
        if controller._child:break
        time.sleep(.01)
    controller.interrupt();thread.join(2)
    assert not thread.is_alive()
    assert isinstance(error[0],InterruptedError)

def test_child_stdout_limit(runtime,tmp_path,monkeypatch):
    import coworker.fp.rendering as r
    monkeypatch.setattr(r,'MAX_OUTPUT',1024)
    script(runtime,monkeypatch,'import sys;sys.stdout.write("x"*10000);sys.stdout.flush()')
    with pytest.raises(ValueError,match='output'):RenderController().run({},tmp_path,timeout=2)

def test_renderer_does_not_receive_credentials_or_node_options(runtime,tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','DO_NOT_FORWARD');monkeypatch.setenv('NODE_OPTIONS','--inspect')
    script(runtime,monkeypatch,'import json,os;print(json.dumps({"ok":True,"keys":[k for k in os.environ if k in ["OPENAI_API_KEY","NODE_OPTIONS","FP_STUDIO_RENDER_CMD"]]}))')
    assert RenderController().run({},tmp_path)['keys']==[]

def test_malformed_output_is_a_failure(runtime,tmp_path,monkeypatch):
    script(runtime,monkeypatch,'print("bad json")')
    with pytest.raises(RuntimeError,match='malformed'):RenderController().run({},tmp_path)
