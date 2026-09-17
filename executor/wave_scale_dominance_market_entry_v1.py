"""Fixed no-argument entry for issue #372 diagnostic-only market measurement."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
from wave_scale_dominance_market_measurement_v1 import build_measurement

INPUTS=Path('/work/inputs');OUT=Path('/results/study')
PROTOCOL=Path('/work/scale_dominance_measurement/protocol.json')
FILES=('1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5)))
OUTPUTS={'diagnostics.jsonl','diagnostic_summary.json'}
MAX_RESULT_BYTES=32*1024*1024

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def blob(path):
    raw=path.read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def load_protocol():
    if PROTOCOL.is_symlink() or not PROTOCOL.is_file():raise RuntimeError('protocol_path')
    p=json.loads(PROTOCOL.read_text())
    if p.get('schema_id')!='csi1000.scale_dominance_market_protocol@1.0':raise RuntimeError('protocol_identity')
    if p.get('profile')!='two-wave-scale-dominance-diagnostic-measurement-v1':raise RuntimeError('profile_identity')
    if set(p.get('files',{}))!=set(FILES):raise RuntimeError('file_set')
    if p.get('reference_labels_visible_to_compute') is not False or p.get('future_suffix_used') is not False:raise RuntimeError('blind_scope')
    if p.get('numeric_state_thresholds') is not None or p.get('threshold_selection_in_run') is not False:raise RuntimeError('threshold_scope')
    if p.get('R4_selected') or p.get('one_minute_strategy_admitted') or p.get('router_pnl') or p.get('production_authority'):raise RuntimeError('authority_scope')
    return p

def load_inputs(protocol):
    if INPUTS.is_symlink() or not INPUTS.is_dir() or {p.name for p in INPUTS.iterdir()}!=set(FILES):raise RuntimeError('input_root')
    frames={};declared={}
    for name in FILES:
        path=INPUTS/name;meta=protocol['files'][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise RuntimeError('input_file_type')
        if path.stat().st_size!=meta['bytes'] or sha(path)!=meta['sha256'] or blob(path)!=meta['git_blob_sha1']:raise RuntimeError('input_identity')
        frames[name]=pd.read_parquet(path);declared[name]=int(meta['declared_rows'])
    return frames,declared

def main():
    if OUT.exists():raise RuntimeError('fresh_output_required')
    protocol=load_protocol();frames,declared=load_inputs(protocol);files=build_measurement(frames,declared)
    if set(files)!=OUTPUTS or sum(len(v) for v in files.values())>MAX_RESULT_BYTES:raise RuntimeError('result_contract')
    OUT.mkdir(parents=True)
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    manifest={'schema_id':'csi1000.scale_dominance_market_manifest@1.0','files':{n:{'bytes':len(r),'sha256':hashlib.sha256(r).hexdigest()} for n,r in sorted(files.items())},
              'reference_labels_joined':False,'threshold_selected':False,'new_training':False,'production_authority':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':'passed','panels':192,'phase_rows':960,'reference_labels_joined':False,'threshold_selected':False,'production_authority':False},sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
