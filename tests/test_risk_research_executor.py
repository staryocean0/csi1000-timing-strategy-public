import base64
import hashlib
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("risk_research_broker", ROOT / "executor/risk_research_broker.py")
risk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk)
GateError = risk.GateError

PRIVATE_REF = "c" * 40
SHA256 = "a" * 64
GIT_SHA = "b" * 40


def git_pair(size=12, digest=GIT_SHA):
    return {"bytes": size, "git_blob_sha1": digest}


def valid_profile(**overrides):
    profile = {
        "private_ref": PRIVATE_REF,
        "source_files": {path: git_pair() for path in risk.SOURCE_PATHS},
        "manifest_path": risk.MANIFEST_PATH,
        "manifest_sha256": SHA256,
        "data_release_tag": risk.base.DATA_RELEASE_TAG,
        "data_asset_name": risk.base.DATA_ASSET_NAME,
        "data_asset_sha256": SHA256,
        "data_asset_bytes": 32,
        "input_files": {"bundle.tar": {"bytes": 16, "sha256": SHA256}},
        "command": list(risk.COMMAND),
        "verify_command": list(risk.VERIFY_COMMAND),
        "command_timeout_seconds": risk.base.COMMAND_TIMEOUT_SECONDS,
        "verification_timeout_seconds": risk.base.VERIFICATION_TIMEOUT_SECONDS,
        "new_training": False,
        "production_authority": False,
    }
    profile.update(overrides)
    return profile


class RiskResearchBrokerTests(unittest.TestCase):
    def test_exact_risk_profile_policy_accepts_only_frozen_surface(self):
        risk.base.validate_profile(valid_profile())
        for key, value in [
            ("private_ref", "main"),
            ("new_training", True),
            ("production_authority", True),
            ("manifest_path", "other.json"),
            ("command", ["arbitrary.py"]),
            ("verify_command", ["arbitrary.py"]),
            ("data_release_tag", "other-release"),
        ]:
            with self.subTest(key=key), self.assertRaises(GateError):
                risk.base.validate_profile(valid_profile(**{key: value}))

    def test_source_set_is_exact_and_pdf_is_rejected(self):
        missing = valid_profile()
        missing["source_files"].pop(next(iter(missing["source_files"])))
        with self.assertRaises(GateError):
            risk.base.validate_profile(missing)
        extra = valid_profile()
        extra["source_files"]["notes.pdf"] = git_pair()
        with self.assertRaises(GateError) as error:
            risk.base.validate_profile(extra)
        self.assertEqual(str(error.exception), "pdf_source_not_allowed")

    def test_git_blob_source_identity_is_recomputed(self):
        raw = b"frozen-private-source\n"
        digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        api = mock.Mock()
        api.request.return_value = {
            "type": "file",
            "encoding": "base64",
            "size": len(raw),
            "sha": digest,
            "content": base64.b64encode(raw).decode(),
        }
        got = risk.fetch_source_file(api, "private/source.py", PRIVATE_REF, git_pair(len(raw), digest))
        self.assertEqual(got, raw)
        bad = bytearray(raw)
        bad[-2] ^= 1
        api.request.return_value = {
            "type": "file",
            "encoding": "base64",
            "size": len(bad),
            "sha": digest,
            "content": base64.b64encode(bytes(bad)).decode(),
        }
        with self.assertRaises(GateError) as error:
            risk.fetch_source_file(api, "private/source.py", PRIVATE_REF, git_pair(len(bad), digest))
        self.assertEqual(str(error.exception), "source_blob_digest_mismatch")

    def test_catalog_load_inherits_only_reviewed_handoff_transport(self):
        loaded = risk.load_profile(risk.PROFILE_NAME)
        self.assertEqual(loaded["command"], risk.COMMAND)
        self.assertEqual(loaded["verify_command"], risk.VERIFY_COMMAND)
        self.assertEqual(set(loaded["source_files"]), set(risk.SOURCE_PATHS))
        self.assertEqual(loaded["data_release_tag"], risk.base.DATA_RELEASE_TAG)
        with self.assertRaises(GateError) as error:
            risk.load_profile("handoff-verify-v1")
        self.assertEqual(str(error.exception), "unknown_profile")

    def test_legacy_broker_file_is_not_the_risk_policy(self):
        legacy_spec = importlib.util.spec_from_file_location("legacy_research_broker_test", ROOT / "executor/research_broker.py")
        legacy = importlib.util.module_from_spec(legacy_spec)
        legacy_spec.loader.exec_module(legacy)
        self.assertEqual(legacy.PROFILE_NAME, "handoff-verify-v1")
        self.assertNotEqual(tuple(legacy.SOURCE_PATHS), tuple(risk.SOURCE_PATHS))
        with self.assertRaises(legacy.GateError):
            legacy.load_profile(risk.PROFILE_NAME)

    def test_router_has_only_reviewed_research_profiles(self):
        entry_spec = importlib.util.spec_from_file_location("research_entry", ROOT / "executor/research_entry.py")
        entry = importlib.util.module_from_spec(entry_spec)
        entry_spec.loader.exec_module(entry)
        self.assertEqual(set(entry.BROKERS), {"handoff-verify-v1", "risk-v2-severity-persistence-v1"})


if __name__ == "__main__":
    unittest.main()
