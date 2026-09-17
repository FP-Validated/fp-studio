"""Run against the actual patched OpenWorker permission engine, not a fixture copy."""
import pytest
from coworker.permissions import Mode, PermissionEngine, write_paths
from coworker.risk import RiskClass, classify
from coworker.tools.fp import WRITE_TOOLS

@pytest.mark.parametrize('name',sorted(WRITE_TOOLS))
def test_fp_writes_have_intrinsic_floor(name,tmp_path):
    assert classify(name,overrides=lambda _:RiskClass.READ)==RiskClass.WRITE_LOCAL
    engine=PermissionEngine(workspace_root=tmp_path,mode=Mode.PLAN)
    result=engine.evaluate(name,{'name':'infographic'})
    assert not result.allowed and not result.needs_user
    assert write_paths(name,{'name':'infographic'})[1]

def test_fp_write_outside_root_via_symlink_is_denied(tmp_path):
    work=tmp_path/'work';outside=tmp_path/'outside';work.mkdir();outside.mkdir()
    (work/'fp').symlink_to(outside,target_is_directory=True)
    engine=PermissionEngine(workspace_root=work,mode=Mode.BYPASS_APPROVALS)
    assert not engine.evaluate('fp_render',{'name':'infographic'}).allowed
