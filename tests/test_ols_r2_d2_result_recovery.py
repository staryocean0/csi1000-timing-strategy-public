from __future__ import annotations

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ols_r2_d2_result_recovery",
    ROOT / "executor" / "ols_r2_d2_result_recovery.py",
)
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)


class OlsR2D2ResultRecoveryTests(unittest.TestCase):
    def test_first_run_identity_is_frozen(self):
        self.assertEqual(RECOVERY.ORIGINAL_RUN_ID, "34969649919-1")
        self.assertEqual(RECOVERY.ORIGINAL_TIP, "a43e65d641d45c4ec7a797b36c62001b94ae180d")
        self.assertEqual(RECOVERY.ORIGINAL_TREE, "fc8d2cd2ff90a38e30e9c2f601cbb445df26e04d")
        self.assertEqual(RECOVERY.ASSET_BYTES, 26230)
        self.assertEqual(
            RECOVERY.ASSET_SHA256,
            "8be2c6e25346765c1f1e3968f8e3e3f44dcefd64b0b84b311b1ef96800b65b9c",
        )
        self.assertEqual(
            RECOVERY.RECOVERED_FILES["study/RESULTS.json"],
            {
                "bytes": 8894,
                "sha256": "684b6382952b3f66e9915f9e07c8590d4af419212e208b924c892f8d2f9a8eaf",
            },
        )

    def test_archive_verifier_accepts_only_receipted_exact_members(self):
        payloads = {
            "study/RESULTS.json": b'{"decision":"fixed"}\n',
            "study/mode_comparison.csv": b"mode,value\nfixed,1\n",
        }
        expected = {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in payloads.items()
        }
        receipt = {"files": expected}
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "results.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for name, raw in payloads.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(raw)
                    tar.addfile(info, io.BytesIO(raw))
            with mock.patch.object(RECOVERY, "RECOVERED_FILES", expected):
                recovered = RECOVERY._verify_archive_and_select(archive, receipt)
        self.assertEqual(recovered, payloads)

    def test_archive_verifier_rejects_unreceipted_member(self):
        payload = b"ok\n"
        expected = {
            "study/RESULTS.json": {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        }
        receipt = {"files": expected}
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "results.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("study/RESULTS.json")
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
                extra = b"nope\n"
                extra_info = tarfile.TarInfo("study/unregistered.txt")
                extra_info.size = len(extra)
                tar.addfile(extra_info, io.BytesIO(extra))
            with mock.patch.object(RECOVERY, "RECOVERED_FILES", expected):
                with self.assertRaises(RECOVERY.GateError):
                    RECOVERY._verify_archive_and_select(archive, receipt)


if __name__ == "__main__":
    unittest.main()
