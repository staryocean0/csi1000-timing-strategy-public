"""Fixed dual-gate broker. Only the standard workflow_dispatch may call this.

No new event trigger, credentials, arbitrary commands, private source paths,
or authority promotion. Shared broker and shared runtime files are unchanged.
Not registered until the reviewed workflow/controller allowlists are updated.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import urllib.parse

HERE=Path(__file__).resolve().parent
PROFILE='two-wave-dual-gates-v1'
PRIVATE_REF='7688ba57206dd29fbef88d8e57475255718471fe'
MANIFEST=HERE.parent/'docs/research/TWO_WAVE_DUAL_GATE_EXECUTION_MANIFEST_V1.json'
SOURCES=('wave_dual_gate_protocol_v1.json','wave_dual_gate_audit_v1.py','wave_dual_gate_probe_v1.py','wave_dual_gate_hierarchy_v1.py','wave_dual_gate_analysis_v1.py',
    'wave_dual_gate_study_v1.py','wave_dual_gate_verifier_v1.py','wave_dual_gate_runtime_v1.py',
    'two_wave_v0800_semantics.py','two_wave_v0800_scale_map.py','wave_skeleton_context_v1.py')
COMMAND=['dual_gate/wave_dual_gate_study_v1.py','--inputs','/work/inputs','--out','/results/study']
VERIFY=['dual_gate/wave_dual_gate_verifier_v1.py','--inputs','/work/inputs','--results','/results/study']


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_profile():
    if MANIFEST.is_symlink():raise ValueError('manifest symlink')
    m=json.loads(MANIFEST.read_text())
    if set(m)!={'schema_id','profile','private_ref','sources','new_training','production_authority'} or m['schema_id']!='csi1000.wave_dual_gate_execution@1.0' or m['profile']!=PROFILE or m['private_ref']!=PRIVATE_REF or set(m['sources'])!=set(SOURCES):
        raise ValueError('unapproved manifest')
    if m['new_training'] is not True or m['production_authority'] is not False:raise ValueError('scope drift')
    for name,meta in m['sources'].items():
        p=HERE/name
        if p.is_symlink() or not p.is_file():raise ValueError('missing frozen source')
        raw=p.read_bytes();blob=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        if set(meta)!={'git_blob_sha1'} or blob!=meta['git_blob_sha1']:raise ValueError('source digest drift')
    return dict(private_ref=PRIVATE_REF,manifest_sha256=digest(MANIFEST),command=COMMAND,verify_command=VERIFY,
                command_timeout_seconds=900,verification_timeout_seconds=900,new_training=True,production_authority=False)


def publish(rb,profile):
    state,root=rb.load_state()
    if not state.get('cleanup_complete'):raise rb.GateError('cleanup_required')
    api=rb.require_private_api();results=root/'results';files=rb.collect_result_files(results)
    archive=root/'results.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in files:tar.add(results/name,arcname=name,recursive=False)
    if archive.stat().st_size>512*1024**2:raise rb.GateError('result_archive_too_large')
    tag='public-research-run-'+state['run_id']
    release=api.request(f'repos/{rb.PRIVATE_REPO}/releases',dict(tag_name=tag,target_commitish=PRIVATE_REF,draft=True,prerelease=True,name='Dual-gate research '+state['run_id'],body='Pending bounded upload verification.'),method='POST')
    uploaded=rb.upload_result(api,release['id'],archive)
    expected='sha256:'+digest(archive);release=api.request(f'repos/{rb.PRIVATE_REPO}/releases/{release["id"]}')
    assets=release.get('assets',[])
    if len(assets)!=1 or uploaded.get('digest')!=expected or assets[0].get('digest')!=expected or assets[0].get('size')!=archive.stat().st_size or assets[0].get('state')!='uploaded':raise rb.GateError('private_archive_readback_failed')
    api.request(f'repos/{rb.PRIVATE_REPO}/releases/{release["id"]}',{'draft':False},method='PATCH')
    receipt=dict(schema_id=rb.RECEIPT_SCHEMA,status='passed' if state.get('compute_success') else 'failed',delivery_status='archive_uploaded_and_verified',public_run_id=state['run_id'],public_source_sha=os.environ['GITHUB_SHA'],private_source_ref=PRIVATE_REF,
        profile=PROFILE,manifest_sha256=profile['manifest_sha256'],files=files,
        archive=dict(release_id=release['id'],tag=tag,sha256=digest(archive),bytes=archive.stat().st_size),new_training=True,production_authority=False)
    payload=(json.dumps(receipt,indent=2)+'\n').encode()
    target=f'repos/{rb.PRIVATE_REPO}/contents/research/public-runs/{state["run_id"]}.json'
    api.request(target,dict(message='Record bounded dual-gate result [skip ci]',branch=state['branch'],content=base64.b64encode(payload).decode()),method='PUT')
    returned=api.request(target+'?ref='+urllib.parse.quote(state['branch'],safe=''))
    if base64.b64decode(returned['content'])!=payload:raise rb.GateError('private_receipt_readback_failed')
    # Fixed private-only readback views; no market rows or public artifacts.
    mirrors={'execution_manifest.json':MANIFEST.read_bytes()}
    if state.get('compute_success'):
        report_path=results/'study'/'report.json'
        if report_path.is_symlink() or not report_path.is_file() or report_path.stat().st_size>2_000_000:raise rb.GateError('report_mirror_size')
        mirrors['report.json']=report_path.read_bytes()
    else:
        diagnostic={}
        for logname in ('compute.log','controller_validation.log','compute_receipt.json'):
            log=results/logname
            if log.is_file() and not log.is_symlink():diagnostic[logname]=log.read_bytes()[-32000:].decode('utf-8',errors='replace')
        mirrors['failure_diagnostic.json']=(json.dumps(diagnostic,ensure_ascii=False)+'\n').encode()
    for name,raw in mirrors.items():
        mirror_target=f'repos/{rb.PRIVATE_REPO}/contents/research/public-runs/{state["run_id"]}/{name}'
        api.request(mirror_target,dict(message='Record fixed private dual-gate readback [skip ci]',branch=state['branch'],content=base64.b64encode(raw).decode()),method='PUT')
        echo=api.request(mirror_target+'?ref='+urllib.parse.quote(state['branch'],safe=''))
        if base64.b64decode(echo['content'])!=raw:raise rb.GateError('private_readback_view_failed')
    if not state.get('compute_success'):raise rb.GateError('compute_failed_consult_private_receipt')
    print('Dual-gate private archive and receipt verified; no production authority.')


def main():
    # Import only when invoked, so synthetic manifest tests need no credentials.
    dependency_blobs={
        'two_wave_v0800_g_bar_time_carrier_broker.py':'d2919987cbe5d3f83a7c8250c2d37a7a91c496be',
        'research_broker.py':'1b4968475fc91a34f53bc08b7b5fdc1bf79862c0',
        'broker.py':'299ab90424e42f76f038d3bad719cb2abeb155dc',
    }
    for name,expected in dependency_blobs.items():
        path=HERE/name
        if path.is_symlink() or not path.is_file():raise ValueError('missing approved broker dependency')
        raw=path.read_bytes()
        if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=expected:raise ValueError('broker dependency drift')
    import two_wave_v0800_g_bar_time_carrier_broker as frozen
    rb=frozen.rb;frozen.require_context();os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('prepare','compute','cleanup','publish'));p.add_argument('profile',choices=(PROFILE,));a=p.parse_args()
    profile=load_profile()
    original_state=rb.load_state;original_docker=rb.docker_command
    def checked_state():
        state,root=original_state()
        if state.get('dual_gate_manifest_sha256')!=digest(MANIFEST):raise rb.GateError('manifest_changed_between_phases')
        if state.get('profile_name')!=PROFILE:raise rb.GateError('wrong_run_profile')
        return state,root
    def prepare_inputs(api,root,fixed):
        del api,fixed
        work=root/'work';work.mkdir();inputs=work/'inputs';inputs.mkdir();scripts=work/'dual_gate';scripts.mkdir()
        for name in SOURCES:shutil.copy2(HERE/name,scripts/name)
        frozen.download_public_data(inputs/'5m_offset_0.parquet')
        return work
    def docker_command(work,results,path,validator=False):
        command=original_docker(work,results,path,validator)
        index=command.index('/run_research_in_container.py')
        command[index]='/work/dual_gate/wave_dual_gate_runtime_v1.py'
        return command
    rb.prepare_inputs=prepare_inputs;rb.load_state=checked_state;rb.docker_command=docker_command
    rb.COMPUTE_HOST_TIMEOUT_SECONDS=960;rb.VALIDATE_HOST_TIMEOUT_SECONDS=960
    if a.phase=='prepare':
        rb.prepare(PROFILE,profile);state,root=original_state();state['dual_gate_manifest_sha256']=digest(MANIFEST);rb.write_state(state)
    elif a.phase=='compute':rb.compute()
    elif a.phase=='cleanup':rb.cleanup()
    else:publish(rb,profile)


if __name__=='__main__':
    try:main()
    except Exception:
        print('Dual-gate execution stopped; consult bounded private evidence.',file=__import__('sys').stderr)
        raise SystemExit(1)
