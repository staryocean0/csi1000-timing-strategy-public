from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "executor" / "risk_phase1b_carrier_inventory_broker.py"
    spec = importlib.util.spec_from_file_location("carrier_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_module()


class CarrierInventoryTests(unittest.TestCase):
    @staticmethod
    def _git_blob_sha1(data: bytes) -> str:
        return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

    def _bundle(self, root: Path):
        payloads = {
            "snapshot/data/market/5m/000688.SH/2026.parquet": b"PAR1-688-identity-only",
            "snapshot/data/market/5m/000852.SH/2026.parquet": b"PAR1-852-identity-only",
            "snapshot/meta/bar_receipts.csv": b"symbol,rows\n000688.SH,1\n",
            "snapshot/data/development/5m_offset_0.parquet": b"offset-working-lead",
            "snapshot/notes.txt": b"not a candidate",
        }
        manifest = {
            "schema": "csi1000_handoff_bundle@1",
            "files": {
                name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in payloads.items()
            },
        }
        manifest_raw = json.dumps(manifest, sort_keys=True).encode()
        bundle = root / "bundle.tar"
        with tarfile.open(bundle, "w") as archive:
            info = tarfile.TarInfo("BUNDLE_MANIFEST.json")
            info.size = len(manifest_raw)
            archive.addfile(info, io.BytesIO(manifest_raw))
            for name, data in payloads.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return bundle, payloads

    def test_inventory_identifies_exact_pair_without_semantic_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, payloads = self._bundle(Path(tmp))
            profile = mod.load_profile()
            profile = copy.deepcopy(profile)
            profile["bundle_member"] = {
                "name": "bundle.tar",
                "bytes": bundle.stat().st_size,
                "sha256": mod.sha(bundle),
            }
            result = mod.inventory_bundle(bundle, profile)
        self.assertEqual(result["status"], "BYTE_CANDIDATES_IDENTIFIED")
        self.assertEqual(result["candidate_counts"]["canonical_000688_2026_5m"], 1)
        self.assertEqual(result["candidate_counts"]["canonical_000852_2026_5m"], 1)
        self.assertEqual(result["candidate_counts"]["bar_receipt_metadata"], 1)
        self.assertEqual(result["candidate_counts"]["working_lead_offset"], 1)
        by_role = {row["role"]: row for row in result["candidates"] if row["role"].startswith("canonical_")}
        self.assertEqual(
            by_role["canonical_000688_2026_5m"]["git_blob_sha1"],
            self._git_blob_sha1(payloads["snapshot/data/market/5m/000688.SH/2026.parquet"]),
        )
        self.assertEqual(
            by_role["canonical_000852_2026_5m"]["git_blob_sha1"],
            self._git_blob_sha1(payloads["snapshot/data/market/5m/000852.SH/2026.parquet"]),
        )
        self.assertFalse(result["controls"]["year_2026_semantic_read"])
        self.assertFalse(result["controls"]["parquet_deserialization"])
        self.assertFalse(result["controls"]["confirmatory_scoring"])

    def test_profile_rejects_scope_broadening(self):
        profile = mod.load_profile()
        broadened = copy.deepcopy(profile)
        broadened["candidate_suffixes"].append("*.parquet")
        with self.assertRaisesRegex(mod.GateError, "candidate_scope_changed"):
            mod.validate_profile(broadened)
        semantic = copy.deepcopy(profile)
        semantic["year_2026_semantic_read"] = True
        with self.assertRaisesRegex(mod.GateError, "semantic_read_not_authorized"):
            mod.validate_profile(semantic)

    def test_source_has_no_parquet_deserializer_or_model_fit(self):
        source = (ROOT / "executor" / "risk_phase1b_carrier_inventory_broker.py").read_text()
        for forbidden in ("read_parquet", "pyarrow", "fit_ridge", "fit_platt", "predict_frozen"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
