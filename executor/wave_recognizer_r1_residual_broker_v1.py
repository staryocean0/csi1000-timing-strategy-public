"""#334 fixed broker; only reviewed public-compute.yml workflow_dispatch.
Reuses frozen R1 transport, not its detector profile. No private Chat writes.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,shutil,urllib.parse
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROFILE='two-wave-r1-residual-clock-audit-v1'
PRIVATE_REF='7688ba57206dd29fbef88d8e57475255718471fe'
MANIFEST=HERE.parent/'docs/research/TWO_WAVE_R1_RESIDUAL_AUDIT_EXECUTION_MANIFEST_V1.json'
SOURCES=('wave_recognizer_r1_residual_probe_v1.py','wave_recognizer_r1_residual_audit_v1.py','wave_recognizer_r1_residual_verifier_v1.py','wave_recognizer_r1_residual_runtime_v1.py','wave_recognizer_r1_residual_protocol_v1.json','wave_recognizer_r1_v1.py','wave_recognizer_r1_v1_entry.py','wave_recognizer_r1_v1_verifier.py','wave_recognizer_r1_v1_runtime.py','wave_recognizer_r1_v1_visuals.py','wave_recognizer_r1_v1_protocol.json','wave_multiscale_dual_gates_v2.py','wave_dual_gate_hierarchy_v1.py','wave_dual_gate_probe_v1.py','two_wave_v0800_scale_map.py','two_wave_v0800_semantics.py')
COMMAND=['r1_residual/wave_recognizer_r1_residual_audit_v1.py','--inputs','/work/inputs','--out','/results/study']
VERIFY=['r1_residual/wave_recognizer_r1_residual_verifier_v1.py','--inputs','/work/inputs','--results','/results/study']

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def blob(p):
    raw=Path(p).read_bytes().replace(b'\r\n',b'\n')
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def load_profile():
    if MANIFEST.is_symlink():raise ValueError('manifest symlink')
    m=json.loads(MANIFEST.read_text())
    if set(m)!={'schema_id','profile','private_ref','sources','new_training','production_authority'} or m['schema_id']!='csi1000.r1_residual_audit_execution@1.0' or m['profile']!=PROFILE or m['private_ref']!=PRIVATE_REF or set(m['sources'])!=set(SOURCES):raise ValueError('unapproved manifest')
    if m['new_training'] is not False or m['production_authority'] is not False:raise ValueError('scope drift')
    for name,meta in m['sources'].items():
        p=HERE/name
        if p.is_symlink() or not p.is_file() or set(meta)!={'git_blob_sha1'} or blob(p)!=meta['git_blob_sha1']:raise ValueError('frozen source identity drift')
    return dict(private_ref=PRIVATE_REF,manifest_sha256=digest(MANIFEST),command=COMMAND,verify_command=VERIFY,command_timeout_seconds=900,verification_timeout_seconds=900,new_training=False,production_authority=False)

def publish(rb,profile):
    import wave_recognizer_r1_v1_broker as transport
    transport.PROFILE=PROFILE;transport.MANIFEST=MANIFEST
    # Frozen transport checks cleanup, hashes archive, reads back private receipt,
    # and mirrors only aggregate report/index and bounded original SVG evidence.
    transport.publish(rb,profile)
    state,root=rb.load_state()
    if not state.get('cleanup_complete') or not state.get('compute_success'):raise rb.GateError('publish_precondition')
    path=root/'results'/'study'/'visual_readback.jsonl'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:raise rb.GateError('visual_readback_bound')
    raw=path.read_bytes();api=rb.require_private_api()
    target=f'repos/{rb.PRIVATE_REPO}/contents/research/public-runs/{state["run_id"]}/visual_readback.jsonl'
    api.request(target,dict(message='Record lossless private visual readback [skip ci]',branch=state['branch'],content=base64.b64encode(raw).decode()),method='PUT')
    echo=api.request(target+'?ref='+urllib.parse.quote(state['branch'],safe=''))
    if base64.b64decode(echo['content'])!=raw:raise rb.GateError('visual_readback_identity_failed')
    print('Residual-clock diagnostic privately returned and verified; no R2 or readiness promotion.')

def main():
    dependencies={'two_wave_v0800_g_bar_time_carrier_broker.py':'d2919987cbe5d3f83a7c8250c2d37a7a91c496be','research_broker.py':'1b4968475fc91a34f53bc08b7b5fdc1bf79862c0','broker.py':'299ab90424e42f76f038d3bad719cb2abeb155dc','wave_recognizer_r1_v1_broker.py':'bcc95a12fbb4dc7086575c677d57e9748023fff9'}
    for name,expected in dependencies.items():
        p=HERE/name
        if p.is_symlink() or not p.is_file() or blob(p)!=expected:raise ValueError('reviewed transport dependency drift')
    import two_wave_v0800_g_bar_time_carrier_broker as frozen
    rb=frozen.rb;frozen.require_context();os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('prepare','compute','cleanup','publish'));p.add_argument('profile',choices=(PROFILE,));a=p.parse_args()
    profile=load_profile();original_state=rb.load_state;original_docker=rb.docker_command
    def checked_state():
        state,root=original_state()
        if state.get('r1_residual_manifest_sha256')!=digest(MANIFEST) or state.get('profile_name')!=PROFILE:raise rb.GateError('run_profile_or_manifest_drift')
        return state,root
    def prepare_inputs(api,root,fixed):
        del api,fixed
        work=root/'work';work.mkdir();inputs=work/'inputs';inputs.mkdir();scripts=work/'r1_residual';scripts.mkdir()
        for name in SOURCES:shutil.copy2(HERE/name,scripts/name)
        frozen.download_public_data(inputs/'5m_offset_0.parquet')
        return work
    def docker_command(work,results,path,validator=False):
        command=original_docker(work,results,path,validator);index=command.index('/run_research_in_container.py')
        command[index]='/work/r1_residual/wave_recognizer_r1_residual_runtime_v1.py'
        return command
    rb.prepare_inputs=prepare_inputs;rb.load_state=checked_state;rb.docker_command=docker_command
    rb.COMPUTE_HOST_TIMEOUT_SECONDS=960;rb.VALIDATE_HOST_TIMEOUT_SECONDS=960
    if a.phase=='prepare':
        rb.prepare(PROFILE,profile);state,root=original_state();state['r1_residual_manifest_sha256']=digest(MANIFEST);rb.write_state(state)
    elif a.phase=='compute':rb.compute()
    elif a.phase=='cleanup':rb.cleanup()
    else:publish(rb,profile)

if __name__=='__main__':
    try:main()
    except Exception:
        print('Residual-clock audit stopped; consult bounded private evidence.',file=__import__('sys').stderr)
        raise SystemExit(1)
