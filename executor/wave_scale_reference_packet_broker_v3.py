"""Bounded standard broker for #363 amended blind reference packet v2 generation."""
from __future__ import annotations
import base64,hashlib,json,os,shutil,urllib.parse
from pathlib import Path
import research_broker as rb

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PROFILE='two-wave-scale-reference-blind-packet-v3'
PRIVATE_REF='7688ba57206dd29fbef88d8e57475255718471fe'
MANIFEST=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_EXECUTION_MANIFEST_V3.json'
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_PROTOCOL_V3_20260917.json'
REFERENCE_PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PROTOCOL_V2_20260917.json'
CARRIER_PROTOCOL=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_PROTOCOL_20260917.json'
STAGE_DIR='two-wave-segmentation-carrier-stage'
COMMAND=['scale_reference_packet/wave_scale_reference_packet_entry_v3.py']
VERIFY=['scale_reference_packet/wave_scale_reference_packet_verifier_v3.py']
SOURCES=(
 'wave_scale_reference_packet_v2.py','wave_scale_reference_packet_entry_v3.py',
 'wave_scale_reference_packet_verifier_v3.py','wave_scale_reference_sampling_v2.py',
 'wave_scale_reference_visuals_v1.py','wave_scale_reference_verifier_v2.py',
 'wave_segmentation_carrier_qualification_v1.py','wave_segmentation_carrier_verifier_v1.py')


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def blob(path):
    raw=path.read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def load_manifest():
    if MANIFEST.is_symlink() or not MANIFEST.is_file():raise rb.GateError('execution_manifest_missing')
    value=json.loads(MANIFEST.read_text())
    required={'schema_id','profile','private_ref','source_blobs','dependency_blobs','broker_blob','stage_blob',
              'protocol_blob','reference_protocol_blob','carrier_protocol_blob','command','verify_command','command_timeout_seconds',
              'verification_timeout_seconds','new_training','production_authority'}
    if set(value)!=required or value['schema_id']!='csi1000.scale_reference_packet_execution@3.0':
        raise rb.GateError('execution_manifest_invalid')
    if value['profile']!=PROFILE or value['private_ref']!=PRIVATE_REF:raise rb.GateError('profile_identity')
    if value['command']!=COMMAND or value['verify_command']!=VERIFY:raise rb.GateError('command_identity')
    if value['command_timeout_seconds']!=600 or value['verification_timeout_seconds']!=600:raise rb.GateError('timeout_identity')
    if value['new_training'] is not False or value['production_authority'] is not False:raise rb.GateError('scope')
    if set(value['source_blobs'])!=set(SOURCES):raise rb.GateError('source_set')
    for name,expected in value['source_blobs'].items():
        if blob(HERE/name)!=expected:raise rb.GateError('source_identity')
    deps={'research_broker.py':'1b4968475fc91a34f53bc08b7b5fdc1bf79862c0',
          'broker.py':'299ab90424e42f76f038d3bad719cb2abeb155dc',
          'run_research_in_container.py':'38dfa9bbcf0a09b328495b4844c82e25c9b5bec8'}
    if value['dependency_blobs']!=deps:raise rb.GateError('dependency_catalog')
    for name,expected in deps.items():
        if blob(HERE/name)!=expected:raise rb.GateError('dependency_identity')
    if blob(HERE/'wave_scale_reference_packet_broker_v3.py')!=value['broker_blob']:raise rb.GateError('broker_identity')
    if blob(HERE/'wave_segmentation_carrier_stage_public.py')!=value['stage_blob']:raise rb.GateError('stage_identity')
    if (blob(PROTOCOL)!=value['protocol_blob'] or blob(REFERENCE_PROTOCOL)!=value['reference_protocol_blob'] or
            blob(CARRIER_PROTOCOL)!=value['carrier_protocol_blob']):
        raise rb.GateError('protocol_identity')
    return value


def load_profile(name):
    if name!=PROFILE:raise rb.GateError('unknown_profile')
    load_manifest()
    return {'private_ref':PRIVATE_REF,'manifest_sha256':digest(MANIFEST),'command':COMMAND,'verify_command':VERIFY,
            'command_timeout_seconds':600,'verification_timeout_seconds':600,
            'new_training':False,'production_authority':False}


def verify_stage():
    root=Path(os.environ['RUNNER_TEMP'])/STAGE_DIR
    receipt_path=root/'stage_receipt.json';inputs=root/'inputs'
    if root.is_symlink() or inputs.is_symlink() or receipt_path.is_symlink():raise rb.GateError('public_stage_link')
    try:
        receipt=json.loads(receipt_path.read_text());carrier=json.loads(CARRIER_PROTOCOL.read_text());protocol=json.loads(PROTOCOL.read_text())
    except Exception:raise rb.GateError('public_stage_invalid') from None
    if receipt.get('schema_id')!='csi1000.segmentation_carrier_public_stage@1.0' or receipt.get('status')!='passed':
        raise rb.GateError('public_stage_invalid')
    if protocol['files']!=carrier['files'] or protocol['external_repository']!=carrier['external_repository'] or protocol['external_ref']!=carrier['external_ref']:
        raise rb.GateError('packet_carrier_identity')
    if receipt.get('private_credentials_used') is not False or receipt.get('repository')!=carrier['external_repository'] or receipt.get('ref')!=carrier['external_ref']:
        raise rb.GateError('public_stage_identity')
    if set(receipt.get('files',{}))!=set(carrier['files']):raise rb.GateError('public_stage_file_set')
    for name,meta in carrier['files'].items():
        path=inputs/name;got=receipt['files'][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise rb.GateError('public_stage_file_type')
        if path.stat().st_size!=meta['bytes'] or digest(path)!=meta['sha256'] or blob(path)!=meta['git_blob_sha1']:
            raise rb.GateError('public_stage_file_identity')
        expected={'bytes':meta['bytes'],'sha256':meta['sha256'],'git_blob_sha1':meta['git_blob_sha1']}
        if got!=expected:raise rb.GateError('public_stage_receipt_identity')
    return inputs,protocol


def prepare_inputs(api,root,profile):
    del api,profile
    staged,protocol=verify_stage();work=root/'work';work.mkdir()
    inputs=work/'inputs';inputs.mkdir();scripts=work/'scale_reference_packet';scripts.mkdir()
    for name in protocol['files']:shutil.copy2(staged/name,inputs/name)
    for name in SOURCES:shutil.copy2(HERE/name,scripts/name)
    shutil.copy2(PROTOCOL,scripts/'protocol.json')
    return work


original_publish=rb.publish


def publish(profile):
    original_publish(profile)
    state,root=rb.load_state();summary=root/'results'/'study'/'packet_summary.json'
    if summary.is_symlink() or not summary.is_file() or summary.stat().st_size>1024*1024:
        raise rb.GateError('aggregate_readback_bound')
    raw=summary.read_bytes();api=rb.require_private_api()
    target=f"repos/{rb.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}/packet_summary.json"
    api.request(target,{'message':'Record scale-reference packet v3 aggregate [skip ci]',
                        'branch':state['branch'],'content':base64.b64encode(raw).decode()},method='PUT')
    echo=api.request(target+'?ref='+urllib.parse.quote(state['branch'],safe=''))
    if base64.b64decode(echo['content'])!=raw:raise rb.GateError('aggregate_readback_identity')
    print('Scale-reference packet aggregate privately mirrored and verified.')


rb.PROFILE_NAME=PROFILE
rb.COMMAND=COMMAND
rb.VERIFY_COMMAND=VERIFY
rb.COMMAND_TIMEOUT_SECONDS=600
rb.VERIFICATION_TIMEOUT_SECONDS=600
rb.COMPUTE_HOST_TIMEOUT_SECONDS=630
rb.VALIDATE_HOST_TIMEOUT_SECONDS=630
rb.load_profile=load_profile
rb.prepare_inputs=prepare_inputs
rb.publish=publish


if __name__=='__main__':rb.run()
