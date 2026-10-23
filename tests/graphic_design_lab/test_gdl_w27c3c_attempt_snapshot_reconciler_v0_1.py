"""W2.7-C3C: strict offline snapshots, never an execution authority."""
import copy
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / 'scripts/graphic_design_lab/worker_runtime'))
import gdl_w27c3c_attempt_snapshot_reconciler_v0_1 as mod


def samples():
    stage = dict(
        schema_version='gdl_w27b_windows_stage_controller_v0_1', mode='verify',
        state=mod.STAGE, task_id=mod.TASK, attempt_id=mod.ATTEMPT,
        archive_sha256=mod.PACKAGE_SHA, archive_bytes=mod.ARCHIVE_BYTES,
        staging_receipt_sha256=mod.RECEIPT_SHA, host='PREPRESS', ssh_account=r'PREPRESS\Work',
        windows_mutation=False, payload_extracted=False, illustrator_execution=False,
        worker_launch_authorized=False, production_ready=False, accepted=False,
        scheduled_tasks_mutated=False, client_files_touched=False, smb_mutation=False,
        cleanup_executed=False,
    )
    host = dict(
        schema_version='gdl_w27c2_native_execution_preflight_v0_1', state=mod.HOST_READY,
        task_id=mod.TASK, attempt_id=mod.ATTEMPT, host='PREPRESS',
        windows_account=r'PREPRESS\Work', archive_sha256=mod.PACKAGE_SHA,
        archive_bytes=mod.ARCHIVE_BYTES, jsx_sha256=mod.JSX_SHA,
        jsx_bytes=mod.JSX_BYTES, staging_receipt_sha256=mod.RECEIPT_SHA,
        session_id=2, preexisting_illustrator_pid=1012,
        windows_mutation=False, payload_extracted=False, illustrator_execution=False,
        com_attach_performed=False, scheduled_tasks_mutated=False,
        worker_launch_authorized=False, dispatch_authorized=False,
        production_ready=False, accepted=False, cleanup_executed=False,
        client_files_touched=False, smb_mutation=False,
    )
    runner = dict(
        schema_version='gdl_w27c3b_native_source_review_v0_1', state=mod.RUNNER_REVIEW,
        task_id=mod.TASK, attempt_id=mod.ATTEMPT,
        package_sha256=mod.PACKAGE_SHA, jsx_sha256=mod.JSX_SHA,
        runner_source_sha256=mod.RUNNER_SHA,
        source_reviewed=True, runtime_verified=False, runner_launch_implemented=False,
        execution_authorized=False, windows_mutation=False, com_attach_performed=False,
        illustrator_execution=False, accepted=False, production_ready=False,
    )
    return [stage, host, runner]


def test_expected_success_snapshot():
    d = mod.reconcile(*samples())
    assert d['state'] == 'HISTORICAL_PREREQUISITES_RECONCILED_AUTHORITY_PENDING'
    assert d['readiness_observation_illustrator_pid'] == 1012
    assert d['snapshots_not_live'] is True
    assert d['fresh_recheck_required_before_any_execution'] is True
    assert d['worker_launch_authorized'] is False
    assert d['dispatch_authorized'] is False
    assert d['retry_authorized'] is False
    assert d['attempt_claim_independently_checked'] is False


@pytest.mark.parametrize('state', [
    'WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED',
    'WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED',
])
def test_waiting_scenario_never_promotes(state):
    x = samples()
    x[1]['state'] = state
    x[1]['preexisting_illustrator_pid'] = None
    x[1]['session_id'] = None if state.startswith('WAITING_FOR_INTERACTIVE') else 2
    d = mod.reconcile(*x)
    assert d['state'] == 'HISTORICAL_HOST_WAITING_NO_DISPATCH'
    assert d['host_readiness_observed'] is False


@pytest.mark.parametrize('component,field,bad', [
    (0,'schema_version','fake'), (0,'mode','stage'), (0,'state','READY_FOR_SYNTHETIC_STAGE'),
    (0,'task_id','wrong-task'), (0,'attempt_id','a0002'), (0,'archive_sha256','0'*64),
    (0,'archive_bytes',5121), (0,'staging_receipt_sha256','1'*64),
    (0,'host','OTHER'), (0,'ssh_account','OTHER'),
    (0,'windows_mutation',True), (0,'payload_extracted',True),
    (0,'illustrator_execution',True), (0,'worker_launch_authorized',True),
    (0,'production_ready',True), (0,'accepted',True),
    (0,'scheduled_tasks_mutated',True), (0,'client_files_touched',True),
    (0,'smb_mutation',True), (0,'cleanup_executed',True),
    (1,'schema_version','wrong'), (1,'state','RUNNING'),
    (1,'task_id','wrong-task'), (1,'attempt_id','a0002'),
    (1,'host','OTHER'), (1,'windows_account','OTHER'),
    (1,'archive_sha256','0'*64), (1,'archive_bytes',1),
    (1,'jsx_sha256','0'*64), (1,'jsx_bytes',3790),
    (1,'staging_receipt_sha256','0'*64),
    (1,'windows_mutation',True), (1,'payload_extracted',True),
    (1,'illustrator_execution',True), (1,'com_attach_performed',True),
    (1,'scheduled_tasks_mutated',True), (1,'worker_launch_authorized',True),
    (1,'dispatch_authorized',True), (1,'production_ready',True),
    (1,'accepted',True), (1,'cleanup_executed',True),
    (1,'client_files_touched',True), (1,'smb_mutation',True),
    (1,'session_id',0), (1,'preexisting_illustrator_pid',0),
    (2,'schema_version','wrong'), (2,'state','RUNNING'),
    (2,'task_id','wrong'), (2,'attempt_id','a0002'),
    (2,'package_sha256','0'*64), (2,'jsx_sha256','0'*64),
    (2,'runner_source_sha256','0'*64),
    (2,'source_reviewed',False), (2,'runtime_verified',True),
    (2,'runner_launch_implemented',True), (2,'execution_authorized',True),
    (2,'windows_mutation',True), (2,'com_attach_performed',True),
    (2,'illustrator_execution',True), (2,'accepted',True),
    (2,'production_ready',True),
])
def test_mutations_rejected(component,field,bad):
    a = samples()
    a[component][field] = bad
    with pytest.raises(mod.SnapshotBlocked):
        mod.reconcile(*a)


@pytest.mark.parametrize('component', [0,1,2])
def test_missing_or_wrong_binding_rejected(component):
    a = samples()
    del a[component]['task_id']
    with pytest.raises(mod.SnapshotBlocked): mod.reconcile(*a)
    a = samples()
    a[component]['task_id'] = None
    with pytest.raises(mod.SnapshotBlocked): mod.reconcile(*a)


@pytest.mark.parametrize('bad', [False,'2',0,None])
def test_session_id_type_rejected(bad):
    a = samples()
    a[1]['session_id'] = bad
    with pytest.raises(mod.SnapshotBlocked): mod.reconcile(*a)


def test_waiting_pid_inconsistent():
    a = samples()
    a[1]['state'] = 'WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED'
    with pytest.raises(mod.SnapshotBlocked): mod.reconcile(*a)


def test_non_mapping():
    for i in range(3):
        a = samples(); a[i] = []
        with pytest.raises(mod.SnapshotBlocked): mod.reconcile(*a)


def test_read_capture(tmp_path):
    root = tmp_path
    p = root/'tmp'/'captures'/'stage.txt'
    p.parent.mkdir(parents=True)
    a = samples()
    p.write_text(json.dumps(a[0])+'\nGDL_W27B_WINDOWS_STAGE='+mod.STAGE+'\n')
    assert mod.read_capture(p, root=root) == a[0]
    p.write_text(json.dumps(a[0]))
    assert mod.read_capture(p, root=root) == a[0]


def test_capture_rejects_trailing_garbage(tmp_path):
    p = tmp_path/'tmp'/'captures'/'stage.txt'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(samples()[0])+'\nEXTRA')
    with pytest.raises(mod.SnapshotBlocked): mod.read_capture(p, root=tmp_path)


def test_capture_rejects_escape_and_file_outside(tmp_path):
    (tmp_path/'tmp').mkdir()
    p = tmp_path/'bad.txt';p.write_text(json.dumps(samples()[0]))
    with pytest.raises(mod.SnapshotBlocked): mod.read_capture(p, root=tmp_path)
    with pytest.raises(mod.SnapshotBlocked): mod.read_capture(tmp_path/'tmp'/'..'/'bad.txt', root=tmp_path)


def test_capture_rejects_symlink(tmp_path):
    root = tmp_path
    p = root/'tmp'/'captures'/'stage.txt'
    p.parent.mkdir(parents=True)
    src = root/'source.txt';src.write_text(json.dumps(samples()[0]))
    p.symlink_to(src)
    with pytest.raises(mod.SnapshotBlocked): mod.read_capture(p, root=root)


def test_capture_rejects_subdirectory(tmp_path):
    p = tmp_path/'tmp'/'captures'/'extra'/'stage.txt';p.parent.mkdir(parents=True)
    p.write_text(json.dumps(samples()[0]))
    with pytest.raises(mod.SnapshotBlocked): mod.read_capture(p, root=tmp_path)


def test_source_check_against_full_snapshot():
    c = mod.check_source()
    assert c['authoritative_for_launch'] is False
    assert c['requires_fresh_pre_execution_recheck'] is True


def test_cli_source_check(capsys):
    assert mod.main(['--mode','source-check']) == 0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_cli_incomplete_blocked(capsys):
    assert mod.main(['--mode','reconcile']) == 2
    assert 'BLOCKED' in capsys.readouterr().err
