"""W2.7-A offline package contract tests; no network, Windows, GUI, SMB or Git mutation."""
from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/gdl_w27_illustrator_task_package_v0_1.py'
FIXTURE = ROOT / 'tests/fixtures/graphic_design_lab/gdl_w27'
spec = importlib.util.spec_from_file_location('gdl_w27_pkg_under_test', SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def mk(tmp_path, monkeypatch):
    root=tmp_path/'repo'
    (root/'tmp').mkdir(parents=True)
    policy=root/'policy.yaml'
    policy.write_text('''windows:
  access_control:
    policy_id: gdl_windows_operator_full_control_dev_v0_3
authority:
  worker_launch: false
  production_publish: false
  automatic_acceptance: false
cleanup:
  no_automatic_deletion: true
''', encoding='utf8')
    monkeypatch.setattr(w,'ROOT',root)
    monkeypatch.setattr(w,'W1',policy)
    monkeypatch.setattr(w,'CONTRACT',ROOT/'coordination/graphic_design_lab/worker_runtime/gdl_w27_task_package_contract_v0_1.json')
    source=root/'tmp'/'w27_source'
    source.mkdir()
    (source/'main.jsx').write_bytes((FIXTURE/'synthetic_task.jsx').read_bytes())
    request=root/'tmp'/'w27_request.json'
    request.write_bytes((FIXTURE/'synthetic_request.json').read_bytes())
    output=root/'tmp'/'w27_output.zip'
    return root,source,request,output


def load(p): return json.loads(p.read_text(encoding='utf8'))


def edit_request(p, fun):
    data=load(p)
    fun(data)
    p.write_text(json.dumps(data,sort_keys=True)+'\n',encoding='utf8')


def test_contract_source_check(tmp_path, monkeypatch):
    mk(tmp_path,monkeypatch)
    assert w.check_static()['scope']=='SYNTHETIC_ONLY'
    assert w.main(['--mode','source-check'])==0


def test_contract_refuses_future_worker_authority(tmp_path, monkeypatch):
    mk(tmp_path, monkeypatch)
    w.W1.write_text(w.W1.read_text().replace('worker_launch: false','worker_launch: true'))
    with pytest.raises(w.PackageBlocked): w.check_static()


def test_prepare_then_verify_offline(tmp_path, monkeypatch):
    root,source,request,output=mk(tmp_path,monkeypatch)
    assert w.main(['--mode','prepare','--request',str(request),'--source-root',str(source),'--output',str(output),'--confirm-synthetic-package'])==0
    assert output.is_file()
    assert output.stat().st_mode & 0o777 == 0o600
    doc,digest=w.inspect_zip(output.read_bytes())
    assert doc['task_id']=='gdl-w27-synthetic-001'
    assert doc['state']==w.STATUS
    assert doc['authority']['dispatch_authorized'] is False
    assert doc['transport']['windows_stage']=='NOT_IMPLEMENTED'
    assert w.main(['--mode','verify','--archive',str(output),'--expected-archive-sha256',digest])==0


def test_deterministic_bytes(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    a=w.run_prepare(request,source,output)
    out2=output.with_name('next.zip')
    b=w.run_prepare(request,source,out2)
    assert output.read_bytes()==out2.read_bytes()
    assert a['archive_sha256']==b['archive_sha256']


def test_existing_attempt_archive_never_overwritten(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    w.run_prepare(request,source,output)
    original=output.read_bytes()
    with pytest.raises(w.PackageBlocked,match='already present'):
        w.run_prepare(request,source,output)
    assert output.read_bytes()==original


def test_incorrect_expected_digest_fails(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    w.run_prepare(request,source,output)
    assert w.main(['--mode','verify','--archive',str(output),'--expected-archive-sha256','f'*64])==2


def test_prepare_requires_explicit_authorization_flag(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    assert w.main(['--mode','prepare','--request',str(request),'--source-root',str(source),'--output',str(output)])==2
    assert not output.exists()


def test_source_check_rejects_extra_flags(tmp_path,monkeypatch):
    mk(tmp_path,monkeypatch)
    assert w.main(['--mode','source-check','--confirm-synthetic-package'])==2


@pytest.mark.parametrize('field,value', [('schema_version','untrusted'),('task_id','bad'),('task_id','../escape'),
    ('attempt_id','a00001'),('adapter_id','acrobat'),('data_class','CUSTOMER'),('inputs',{}),
    ('expected_outputs',[]),('authority',{'worker_launch':True,'production_publish':False,'automatic_accept':False})])
def test_request_top_guards(tmp_path,monkeypatch,field,value):
    _,source,request,output=mk(tmp_path,monkeypatch)
    edit_request(request,lambda d:d.update({field:value}))
    with pytest.raises(w.PackageBlocked): w.run_prepare(request,source,output)
    assert not output.exists()


@pytest.mark.parametrize('path', ['../outside.jsx','/tmp/input/main.jsx','input/../main.jsx','input\\main.jsx','input//main.jsx','input/.hidden.jsx','input/MAIN.js','input/main.jsx/','input/main.jsx:evil'])
def test_script_path_guards(tmp_path,monkeypatch,path):
    _,source,request,output=mk(tmp_path,monkeypatch)
    edit_request(request,lambda d:d['script'].update({'path':path}))
    with pytest.raises(w.PackageBlocked): w.run_prepare(request,source,output)


def test_payload_sha_fails_closed(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'main.jsx').write_text('different JSX')
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_symlink_asset_forbidden(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'main.jsx').unlink()
    target=tmp_path/'other.jsx'
    target.write_bytes((FIXTURE/'synthetic_task.jsx').read_bytes())
    (source/'main.jsx').symlink_to(target)
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_hardlink_asset_forbidden(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'copy.jsx').hardlink_to(source/'main.jsx')
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_extra_asset_roundtrip(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'assets').mkdir()
    (source/'assets'/'picture.svg').write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    blob=(source/'assets'/'picture.svg').read_bytes()
    edit_request(request,lambda d:d['inputs'].append({'path':'input/assets/picture.svg','bytes':len(blob),'sha256':w.sha(blob)}))
    r=w.run_prepare(request,source,output)
    manifest,digest=w.inspect_zip(output.read_bytes())
    assert r['payload_count']==2
    assert manifest['inputs'][0]['path']=='input/assets/picture.svg'
    assert digest==r['archive_sha256']


def test_duplicate_asset_path_forbidden(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'assets').mkdir()
    (source/'assets'/'sample.txt').write_bytes(b'x')
    e={'path':'input/assets/sample.txt','bytes':1,'sha256':w.sha(b'x')}
    edit_request(request,lambda d:d['inputs'].extend([e,e]))
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_output_must_include_native_and_result(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    edit_request(request,lambda d:d['expected_outputs'].pop())
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_zip_member_integrity_detected(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    w.run_prepare(request,source,output)
    raw=output.read_bytes()
    assert b'FORPRINT_W27_PACKAGE_ONLY' in raw
    with pytest.raises(w.PackageBlocked):
        w.inspect_zip(raw.replace(b'FORPRINT_W27_PACKAGE_ONLY',b'FORPRINT_W27_PACKAGE_FAKE',1))


def test_unexpected_zip_member_rejected(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    w.run_prepare(request,source,output)
    with zipfile.ZipFile(io.BytesIO(output.read_bytes()),'r') as z:
        data={i.filename:z.read(i) for i in z.infolist()}
    data['evil.txt']=b'bad'
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:
        for name,blob in data.items():
            info,_=w.zip_member(name,blob)
            z.writestr(info,blob)
    with pytest.raises(w.PackageBlocked):w.inspect_zip(raw.getvalue())


def test_tampered_authority_manifest_rejected(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    w.run_prepare(request,source,output)
    with zipfile.ZipFile(io.BytesIO(output.read_bytes()),'r') as z:
        m=json.loads(z.read('task_manifest.json'))
        b=z.read('input/main.jsx')
    m['authority']['worker_launch']=True
    raw=w.archive_bytes(m,{'input/main.jsx':b})
    with pytest.raises(w.PackageBlocked):w.inspect_zip(raw)


def test_safe_rel_path_case_collision(tmp_path,monkeypatch):
    _,source,request,output=mk(tmp_path,monkeypatch)
    (source/'assets').mkdir()
    (source/'assets'/'SAMple.txt').write_bytes(b'x')
    (source/'assets'/'sample.txt').write_bytes(b'x')
    a={'path':'input/assets/SAMple.txt','bytes':1,'sha256':w.sha(b'x')}
    b={'path':'input/assets/sample.txt','bytes':1,'sha256':w.sha(b'x')}
    edit_request(request,lambda d:d['inputs'].extend([a,b]))
    with pytest.raises(w.PackageBlocked):w.run_prepare(request,source,output)


def test_does_not_import_ssh_windows_or_execute(tmp_path,monkeypatch):
    mk(tmp_path,monkeypatch)
    source=SCRIPT.read_text()
    for needle in ('subprocess.run(', 'ssh_command(', 'DoJavaScript', 'Start-ScheduledTask', 'os.system(', 'shutil.rmtree(', 'eval(', 'exec('):
        assert needle not in source
