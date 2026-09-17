import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
from tests.segmentation_carrier_registration_support import PACKET_V3_PROFILE as PROFILE,PACKET_V3_BROKER as BROKER,strip_packet_v3_workflow,strip_packet_v3_controller
import wave_scale_reference_packet_broker_v3 as broker
MANIFEST=ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_EXECUTION_MANIFEST_V3.json"
PROTOCOL=ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_PROTOCOL_V3_20260917.json"
WORKFLOW=ROOT/".github/workflows/public-compute.yml";CONTROLLER=ROOT/".github/workflows/controller-dispatch.yml"

def blob(path):
 raw=Path(path).read_bytes();return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

class PacketV3RegistrationTests(unittest.TestCase):
 def workflow(self):return yaml.load(WORKFLOW.read_text(),Loader=yaml.BaseLoader)
 def test_route_is_exact_append_to_v2_parent(self):
  w=strip_packet_v3_workflow(WORKFLOW.read_text()).encode();c=strip_packet_v3_controller(CONTROLLER.read_text()).encode()
  self.assertEqual(hashlib.sha1(b"blob "+str(len(w)).encode()+b"\0"+w).hexdigest(),"83e7c0d7d37b3d6b6279703963dbc19e9438ff12")
  self.assertEqual(hashlib.sha1(b"blob "+str(len(c)).encode()+b"\0"+c).hexdigest(),"c2da1da57daa1e3b9148199620f2b72a5a67bc71")
 def test_secret_surface_and_four_routes(self):
  doc=self.workflow();self.assertEqual(WORKFLOW.read_text().count("secrets.FACTORLAB_PRIVATE_TOKEN"),2)
  steps=doc["jobs"]["execute"]["steps"];r=[x for x in steps if BROKER in x.get("run","")]
  self.assertEqual([x["name"] for x in r],["Prepare fixed private inputs","Compute without private credentials","Stop owned container before credentials return","Return verified results privately"])
  for phase,step in zip(("prepare","compute","cleanup","publish"),r):self.assertEqual(step["run"].count(BROKER+" "+phase+" "+PROFILE),1)
  for step in r[1:3]:self.assertNotIn("env",step)
 def test_manifest_and_reused_v2_science_identities(self):
  m=json.loads(MANIFEST.read_text());self.assertEqual(m["profile"],PROFILE)
  for name,sha in m["source_blobs"].items():self.assertEqual(blob(ROOT/"executor"/name),sha,name)
  self.assertEqual(blob(ROOT/"executor/wave_scale_reference_packet_broker_v3.py"),m["broker_blob"])
  self.assertEqual(blob(PROTOCOL),m["protocol_blob"])
  self.assertEqual(m["source_blobs"]["wave_scale_reference_packet_v2.py"],"90b226723098188185725576e4caffa37993d2d4")
  self.assertEqual(m["source_blobs"]["wave_scale_reference_sampling_v2.py"],"7cc243a1cee058b15d96db82a123e466de63571b")
 def test_protocol_freezes_reason_only_amendment(self):
  p=json.loads(PROTOCOL.read_text());self.assertEqual(p["amendment_issue"],366);self.assertEqual(p["amendment_scope"],"INDEPENDENT_VERIFIER_REASON_TAXONOMY_ONLY")
  self.assertEqual(p["producer_sampling_semantics"],"EXACT_V2_REUSE_NO_CHANGE")
  self.assertEqual(p["known_v2_producer_summary"]["anchor_context_exclusions"],{"context_causal_flat_fill":43,"context_support":1})
  self.assertEqual(p["failed_parent"]["full_inventory_sha256"],"32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206")
  self.assertFalse(p["primary_labels_frozen"]);self.assertIsNone(p["numeric_state_thresholds"]);self.assertFalse(p["production_authority"])
 def test_controller_exact_title(self):
  t=CONTROLLER.read_text();self.assertEqual(t.count("github.event.issue.title == 'controller: "+PROFILE+"'"),1);self.assertEqual(t.count("profile='"+PROFILE+"'"),1)
 def test_broker_profile_and_commands(self):
  m=json.loads(MANIFEST.read_text());got=broker.load_profile(PROFILE);self.assertEqual(got["command"],m["command"]);self.assertEqual(got["verify_command"],m["verify_command"]);self.assertFalse(got["production_authority"])
 def test_checkpoint_preserves_prior19_and_failed_v2(self):
  cp=json.loads((ROOT/"docs/research/TWO_WAVE_SCALE_REFERENCE_PACKET_V3_CHECKPOINT_20260917.json").read_text());l=json.loads((ROOT/"docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json").read_text())
  raw=json.dumps(l["ordered_lineage"][:19],sort_keys=True,separators=(",",":")).encode();self.assertEqual(hashlib.sha256(raw).hexdigest(),cp["history_guard"]["prior_19_lineage_sha256"])
  self.assertEqual(l["ordered_lineage"][19]["formal_run"],"35207642041-1");self.assertEqual(l["ordered_lineage"][19]["status"],"FAILED_CLOSED_VERIFIER_REASON_SUMMARY_MISMATCH");self.assertEqual(l["ordered_lineage"][20]["issue"],366)
 def test_independent_verifier_does_not_import_producer(self):
  t=(ROOT/"executor/wave_scale_reference_packet_verifier_v3.py").read_text();self.assertNotIn("wave_scale_reference_packet_v2",t);self.assertNotIn("wave_scale_reference_packet_entry_v3",t);self.assertIn("context_causal_flat_fill",t);self.assertIn("context_ineligible",t)
 def test_isolated_stage_import_closure(self):
  m=json.loads(MANIFEST.read_text());pkgs=[str(Path(x).resolve()) for x in sys.path if x and ("site-packages" in Path(x).parts or "dist-packages" in Path(x).parts)]
  with tempfile.TemporaryDirectory() as d:
   stage=Path(d)/"stage";stage.mkdir()
   for name in m["source_blobs"]:shutil.copy2(ROOT/"executor"/name,stage/name)
   code="import sys,json;from pathlib import Path;p=Path(sys.argv[1]);sys.path[:0]=[str(p),*json.loads(sys.argv[2])];import wave_scale_reference_packet_entry_v3 as a;import wave_scale_reference_packet_verifier_v3 as b;assert Path(a.__file__).resolve().parent==p and Path(b.__file__).resolve().parent==p;print('V3_STAGE_PASS')"
   r=subprocess.run([sys.executable,"-I","-c",code,str(stage),json.dumps(pkgs)],cwd=d,check=True,capture_output=True,text=True,timeout=30);self.assertEqual(r.stdout.strip(),"V3_STAGE_PASS")
if __name__=="__main__":unittest.main()
