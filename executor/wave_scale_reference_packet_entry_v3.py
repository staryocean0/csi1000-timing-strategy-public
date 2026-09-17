"""Fixed no-argument entry for #363 amended blind reference packet v2 generation."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
import pandas as pd
from wave_scale_reference_packet_v2 import build_packet,result_manifest

INPUTS=Path('/work/inputs')
OUT=Path('/results/study')
PROTOCOL=Path('/work/scale_reference_packet/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
PANEL_RE=re.compile(r'^panels/[0-9a-f]{20}_(A150|A300|B300)\.svg$')
JSON_NAMES={'full_inventory.json','blind_inventory.json','panel_manifest.json','packet_summary.json'}
MAX_RESULT_BYTES=64*1024*1024


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def blob(path):
    raw=path.read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def load_protocol():
    if PROTOCOL.is_symlink() or not PROTOCOL.is_file():raise RuntimeError('protocol_path')
    p=json.loads(PROTOCOL.read_text())
    if p.get('schema_id')!='csi1000.scale_reference_packet_protocol@3.0':raise RuntimeError('protocol_identity')
    if p.get('profile')!='two-wave-scale-reference-blind-packet-v3':raise RuntimeError('profile_identity')
    if set(p.get('files',{}))!=set(FILES):raise RuntimeError('file_set')
    r=p.get('reference_contract',{})
    if r.get('primary_panels')!=192 or r.get('contexts_trading_minutes')!=[150,300]:raise RuntimeError('reference_contract')
    if r.get('future_suffix_generated') is not False or r.get('replace_unsupported_anchor') is not False:raise RuntimeError('scope')
    if p.get('numeric_state_thresholds') is not None or p.get('primary_labels_frozen') is not False:raise RuntimeError('threshold_or_label_scope')
    if p.get('outcomes_used') or p.get('R4_selected') or p.get('one_minute_strategy_admitted') or p.get('router_pnl') or p.get('production_authority'):
        raise RuntimeError('authority_scope')
    return p


def load_inputs(protocol):
    if INPUTS.is_symlink() or not INPUTS.is_dir():raise RuntimeError('input_root')
    if {p.name for p in INPUTS.iterdir()}!=set(FILES):raise RuntimeError('input_directory_set')
    frames={};declared={}
    for name in FILES:
        path=INPUTS/name;meta=protocol['files'][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise RuntimeError('input_file_type')
        if path.stat().st_size!=meta['bytes'] or sha(path)!=meta['sha256'] or blob(path)!=meta['git_blob_sha1']:
            raise RuntimeError('input_identity')
        frames[name]=pd.read_parquet(path);declared[name]=int(meta['declared_rows'])
    return frames,declared


def allowed_name(name):
    return name in JSON_NAMES or PANEL_RE.fullmatch(name) is not None


def main():
    if OUT.exists():raise RuntimeError('fresh_output_required')
    protocol=load_protocol();frames,declared=load_inputs(protocol)
    files=build_packet(frames,declared)
    if set(name for name in files if name.endswith('.json'))!=JSON_NAMES:raise RuntimeError('json_output_set')
    if any(not allowed_name(name) for name in files):raise RuntimeError('output_name')
    if sum(len(raw) for raw in files.values())>MAX_RESULT_BYTES:raise RuntimeError('result_bound')
    OUT.mkdir(parents=True)
    for name,raw in files.items():
        target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() or target.is_symlink():raise RuntimeError('output_collision')
        target.write_bytes(raw)
    manifest=result_manifest(files)
    if len(manifest)>8*1024*1024:raise RuntimeError('manifest_bound')
    (OUT/'manifest.json').write_bytes(manifest)
    print(json.dumps({'status':'passed','panels':192,'panel_files':576,
                      'labels_frozen':False,'diagnostic_scores_measured':False,
                      'production_authority':False},sort_keys=True,separators=(',',':')))


if __name__=='__main__':main()
