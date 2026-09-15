from __future__ import annotations
import base64,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location('_rb_rel_mirror',HERE/'research_broker.py');base=importlib.util.module_from_spec(_s);_s.loader.exec_module(base);GateError=base.GateError
PROFILE='risk-v2-15m-continuous-reliability-score-v1';FILES=('SUMMARY.json','RELIABILITY_RESULT.json','RELIABILITY_ENDPOINTS.csv')
def main():
    state,root=base.load_state()
    if state.get('profile_name')!=PROFILE or state.get('compute_success') is not True or state.get('cleanup_complete') is not True:raise GateError('reliability_state_not_mirrorable')
    api=base.require_private_api();study=root/'results'/'study'
    for name in FILES:
        p=study/name
        if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=512*1024:raise GateError('reliability_mirror_file_invalid')
        raw=p.read_bytes()
        try:raw.decode('utf-8')
        except UnicodeDecodeError:raise GateError('reliability_mirror_not_utf8') from None
        target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(target,{'message':'Record verified 15m reliability score [skip ci]','branch':state['branch'],'content':base64.b64encode(raw).decode('ascii')},method='PUT')
        got=api.request(target+'?ref='+base.urllib.parse.quote(state['branch'],safe=''))
        if base64.b64decode(got['content'])!=raw:raise GateError('reliability_mirror_readback_failed')
    print('Verified reliability score outputs mirrored privately.')
if __name__=='__main__':main()
