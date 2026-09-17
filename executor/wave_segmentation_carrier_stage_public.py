"""Stage the six immutable public Development carriers for issue #352.

Runs before private credentials exist. No arbitrary URL/path inputs.
"""
from __future__ import annotations
import hashlib, json, os, shutil, urllib.parse, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROTOCOL=HERE.parent/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_PROTOCOL_20260917.json'
REPO='staryocean0/factorlab-two-wave-strategy-lab'
REF='152ae1ef11a04bb3b434da25025794db7a706c81'
STAGE_DIR='two-wave-segmentation-carrier-stage'
MAX_FILE=16*1024*1024
MAX_TOTAL=40*1024*1024

def git_blob(raw:bytes)->str:
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def main():
    if os.environ.get('FACTORLAB_PRIVATE_TOKEN'):
        raise RuntimeError('private_token_must_not_reach_public_stage')
    p=json.loads(PROTOCOL.read_text())
    if p.get('schema_id')!='csi1000.segmentation_carrier_qualification_protocol@1.0' or p.get('external_repository')!=REPO or p.get('external_ref')!=REF:
        raise RuntimeError('protocol_identity')
    files=p.get('files',{})
    expected={'1m_official.parquet',*(f'5m_offset_{i}.parquet' for i in range(5))}
    if set(files)!=expected or sum(v['bytes'] for v in files.values())>MAX_TOTAL:
        raise RuntimeError('source_set')
    root=Path(os.environ['RUNNER_TEMP'])/STAGE_DIR
    if root.exists():shutil.rmtree(root)
    inputs=root/'inputs';inputs.mkdir(parents=True)
    receipt_files={}
    total=0
    for name in sorted(files):
        meta=files[name]
        if not 1<=meta['bytes']<=MAX_FILE:raise RuntimeError('file_bound')
        path='data/development/'+name
        url=f"https://raw.githubusercontent.com/{REPO}/{REF}/{urllib.parse.quote(path,safe='/')}"
        req=urllib.request.Request(url,headers={'User-Agent':'csi1000-segmentation-carrier-stage/1'})
        with urllib.request.urlopen(req,timeout=60) as r:
            raw=r.read(MAX_FILE+1)
        if len(raw)!=meta['bytes'] or hashlib.sha256(raw).hexdigest()!=meta['sha256'] or git_blob(raw)!=meta['git_blob_sha1']:
            raise RuntimeError('source_identity')
        total+=len(raw)
        if total>MAX_TOTAL:raise RuntimeError('total_bound')
        target=inputs/name
        target.write_bytes(raw)
        receipt_files[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob_sha1':git_blob(raw)}
    receipt={'schema_id':'csi1000.segmentation_carrier_public_stage@1.0','status':'passed','repository':REPO,'ref':REF,
             'files':receipt_files,'total_bytes':total,'private_credentials_used':False,'production_authority':False}
    (root/'stage_receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('Fixed public segmentation carriers staged and byte-verified without private credentials.')
if __name__=='__main__':main()
