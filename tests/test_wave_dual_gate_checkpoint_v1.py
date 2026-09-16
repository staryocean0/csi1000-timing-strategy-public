"""Control-plane checkpoint must not leak market data or imply authority."""
import json
from pathlib import Path
import unittest
class CheckpointTests(unittest.TestCase):
    def test_fixed_private_evidence_and_closed_authorities(self):
        root=Path(__file__).resolve().parents[1]
        d=json.loads((root/'docs/research/TWO_WAVE_DUAL_GATE_RUN_CHECKPOINT_20260916.json').read_text(encoding='utf-8'))
        self.assertEqual(d['run_id'],35065802258)
        self.assertEqual(d['event'],'workflow_dispatch')
        self.assertEqual(d['run_head_sha'],d['source_merge'])
        self.assertTrue(all(s=='success' for s in d['phases'].values()))
        for key in ('fresh_oos','public_market_results_published','row_level_results_read_by_chat','trade_authority','production_authority','state_publication_authority'):
            self.assertFalse(d[key])
        self.assertEqual(d['open_upstream_issues'],[274,277])
        self.assertNotIn('A',d);self.assertNotIn('B',d)
        self.assertEqual(d['private_evidence']['repository'],'staryocean0/csi1000-timing-strategy-private')
