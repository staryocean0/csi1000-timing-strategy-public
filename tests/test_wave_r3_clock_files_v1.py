"""Adversarial synthetic file-contract tests for #345; no real carrier access."""
import copy
import gzip
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from test_wave_r3_clock_v1 import waves_path, bars
from wave_r3_clock_entry_v1 import emit_bundle, main as entry_main
from wave_r3_clock_verifier_v1 import verify_bundle, main as verifier_main
from wave_r3_clock_files_v1 import (encode, decode, fresh_root, file_limit, no_links,
    write_trace, read_trace, write_manifest, verify_manifest, read_json, write_bytes)

class FileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory()
        cls.b=bars(list(waves_path().close)+[200.]*52)
        cls.original=Path(cls.fixture.name)/'study'
        emit_bundle(cls.b,cls.original,formal=False)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.out=Path(self.folder.name)/'study'
        shutil.copytree(self.original,self.out)

    def reseal(self):
        (self.out/'manifest.json').unlink()
        write_manifest(self.out)

    def rewrite_json(self,name,obj):
        (self.out/name).write_bytes(encode(obj))
        self.reseal()

    def verify(self):
        return verify_bundle(self.b,self.out,formal=False)

    def test_roundtrip_includes_resets_and_independent_prefixes(self):
        value=self.verify()
        self.assertEqual(value['status'],'passed')
        self.assertTrue(value['causality_passed'])
        self.assertGreater(value['independent_cases']['nonedge_cases'], -1)
        self.assertGreater(len(read_json(self.out,'events.json')['resets']),0)
        self.assertGreaterEqual(value['prefix_cutoffs_checked'],8)
        self.assertFalse(value['R4_selected'])

    def test_formal_parent_gate_rejects_synthetic_substitution(self):
        with self.assertRaises(ValueError):verify_bundle(self.b,self.out,formal=True)

    def test_entry_accepts_no_runtime_argument(self):
        with patch.object(sys,'argv',['entry','/tmp/other']):
            with self.assertRaises(ValueError):entry_main()

    def test_verifier_accepts_no_runtime_argument(self):
        with patch.object(sys,'argv',['verifier','--inputs','/tmp/other']):
            with self.assertRaises(ValueError):verifier_main()

    def test_fresh_output_cannot_overwrite(self):
        before=(self.out/'report.json').read_bytes()
        with self.assertRaises(FileExistsError):emit_bundle(self.b,self.out,formal=False)
        self.assertEqual(before,(self.out/'report.json').read_bytes())

    def test_absolute_traversal_and_unknown_names_rejected(self):
        for name in ('../escape.json','/tmp/escape.json','visuals/../report.json','extra.json','visuals/case-X-0.svg'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):file_limit(name)

    def test_oversized_named_file_rejected_before_write(self):
        with self.assertRaises(ValueError):write_bytes(self.out,'parent/manifest.json',b'x'*500001)

    def test_root_symlink_rejected(self):
        link=Path(self.folder.name)/'link';link.symlink_to(self.out,target_is_directory=True)
        with self.assertRaises(ValueError):verify_bundle(self.b,link,formal=False)

    def test_ancestor_symlink_rejected(self):
        link=Path(self.folder.name)/'link';link.symlink_to(self.out,target_is_directory=True)
        with self.assertRaises(ValueError):no_links(link/'parent'/'report.json')

    def test_file_symlink_rejected(self):
        f=self.out/'report.json';f.unlink();f.symlink_to(self.original/'report.json')
        with self.assertRaises(ValueError):verify_manifest(self.out)

    def test_extra_file_rejected(self):
        (self.out/'other.json').write_text('{}')
        with self.assertRaises(ValueError):verify_manifest(self.out)

    def test_extra_empty_directory_rejected(self):
        (self.out/'other').mkdir()
        with self.assertRaises(ValueError):verify_manifest(self.out)

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}'):
            with self.assertRaises(ValueError):decode(raw)

    def test_gzip_long_line_is_bounded(self):
        with gzip.open(self.out/'trace.jsonl.gz','wb') as f:f.write(b'x'*9000+b'\n')
        with self.assertRaises(ValueError):read_trace(self.out)

    def test_gzip_row_count_is_bounded(self):
        with gzip.open(self.out/'trace.jsonl.gz','wb') as f:f.write(b'{}\n'*4)
        with patch('wave_r3_clock_files_v1.MAX_ROWS',3):
            with self.assertRaises(ValueError):read_trace(self.out)

    def test_gzip_decoded_bytes_are_bounded(self):
        with gzip.open(self.out/'trace.jsonl.gz','wb') as f:f.write(b'{}\n'*4)
        with patch('wave_r3_clock_files_v1.MAX_TRACE_BYTES',8):
            with self.assertRaises(ValueError):read_trace(self.out)

    def test_gzip_partial_line_rejected(self):
        with gzip.open(self.out/'trace.jsonl.gz','wb') as f:f.write(b'{}')
        with self.assertRaises(ValueError):read_trace(self.out)

    def test_manifest_self_rehash_cannot_hide_trace_tamper(self):
        rows=read_trace(self.out);rows[30]['post']['candidate']=-1
        (self.out/'trace.jsonl.gz').unlink();write_trace(self.out,rows);self.reseal()
        with self.assertRaises(ValueError):self.verify()

    def test_joint_event_and_trace_omission_rejected(self):
        rows=read_trace(self.out)[:-1]
        (self.out/'trace.jsonl.gz').unlink();write_trace(self.out,rows)
        e=read_json(self.out,'events.json');e['pivots'].pop()
        self.rewrite_json('events.json',e)
        with self.assertRaises(ValueError):self.verify()

    def test_resealed_latency_tamper_rejected(self):
        rows=read_json(self.out,'latency.json');rows[0]['counter_survival']+=1
        self.rewrite_json('latency.json',rows)
        with self.assertRaises(ValueError):self.verify()

    def test_resealed_event_tamper_rejected(self):
        e=read_json(self.out,'events.json');e['resets'][0]['bar_index']-=1
        self.rewrite_json('events.json',e)
        with self.assertRaises(ValueError):self.verify()

    def test_unknown_report_field_rejected(self):
        value=read_json(self.out,'report.json');value['unreviewed']=True
        self.rewrite_json('report.json',value)
        with self.assertRaises(ValueError):self.verify()

    def test_joint_summary_label_bug_rejected_by_independent_predicates(self):
        value=read_json(self.out,'report.json')
        value['reset_classification_counts']={'UNSUPPORTED_LABEL':1}
        self.rewrite_json('report.json',value)
        with patch('wave_r3_clock_verifier_v1.summarize',return_value=value):
            with self.assertRaisesRegex(ValueError,'independent reset count'):self.verify()

    def test_resealed_parent_tamper_rejected(self):
        value=read_json(self.out,'parent/report.json');value['numeric_gate_pass']=True
        self.rewrite_json('parent/report.json',value)
        with self.assertRaises(ValueError):self.verify()

    def test_resealed_visual_tamper_rejected(self):
        svg=next((self.out/'visuals').glob('*.svg'))
        svg.write_bytes(svg.read_bytes()+b'<!-- changed -->');self.reseal()
        with self.assertRaises(ValueError):self.verify()

    def test_scope_promotion_rejected(self):
        value=read_json(self.out,'report.json');value['R4_selected']=True
        self.rewrite_json('report.json',value)
        with self.assertRaises(ValueError):self.verify()

if __name__=='__main__':unittest.main()
