import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from test_research_executor import research_broker as b,valid_profile,synthetic_bundle,contents_payload

class PartsTests(unittest.TestCase):
    def test_part_identity_order_and_sizes_are_fixed(self):
        p=valid_profile();p['asset_parts']=[{'name':b.DATA_ASSET_NAME+'.part-000','bytes':32,'sha256':'a'*64}]
        b.validate_profile(p)
        for key,value in [('name','arbitrary.bin'),('bytes',33),('sha256','invalid')]:
            q=copy.deepcopy(p);q['asset_parts'][0][key]=value
            with self.assertRaises(b.GateError):b.validate_profile(q)

    def test_split_recombines_original_archive_and_rejects_tampering(self):
        profile,sources,archive=synthetic_bundle();cut=len(archive)//2
        rawparts=[archive[:cut],archive[cut:]]
        profile['asset_parts']=[{'name':b.DATA_ASSET_NAME+f'.part-{i:03d}','bytes':len(x),
            'sha256':hashlib.sha256(x).hexdigest()} for i,x in enumerate(rawparts)]
        b.validate_profile(profile)
        class API:
            tamper=False
            def request(self,path,*args,**kwargs):
                if '/contents/' in path:
                    name=path.split('/contents/')[1].split('?ref=')[0]
                    return contents_payload(sources[name])
                if '/releases/tags/' in path:
                    return {'draft':False,'assets':[{'name':p['name'],'id':i,'state':'uploaded',
                        'size':p['bytes'],'digest':'sha256:'+p['sha256']} for i,p in enumerate(profile['asset_parts'])]}
                i=int(path.rsplit('/',1)[1]);data=rawparts[i]
                if self.tamper and i==1:data=b'X'*len(data)
                kwargs['binary_path'].write_bytes(data)
        with tempfile.TemporaryDirectory() as d:
            work=b.prepare_inputs(API(),Path(d),profile)
            self.assertTrue((work/'inputs/bundle.tar').is_file())
        with tempfile.TemporaryDirectory() as d:
            api=API();api.tamper=True
            with self.assertRaises(b.GateError):b.prepare_inputs(api,Path(d),profile)
