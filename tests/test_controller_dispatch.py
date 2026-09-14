from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControllerDispatchTests(unittest.TestCase):
    def test_controller_is_owner_only_and_allowlisted(self):
        text = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertIn('types: [opened]', text)
        self.assertIn('github.event.issue.user.login == github.repository_owner', text)
        self.assertIn('actions: write', text)
        self.assertIn('public-compute.yml/dispatches', text)
        self.assertIn("-f ref='cloud-workspace-v1'", text)
        for profile in ('runtime-smoke', 'handoff-verify-v1', 'risk-v2-severity-persistence-v1'):
            self.assertIn(f'controller: {profile}', text)
            self.assertIn(f"profile='{profile}'", text)

    def test_controller_does_not_compute(self):
        text = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertNotIn('actions/checkout', text)
        self.assertNotIn('docker ', text)
        self.assertNotIn('executor/', text)
        self.assertNotIn('environment:', text)

    def test_standard_compute_stays_workflow_dispatch_only(self):
        text = (ROOT / '.github/workflows/public-compute.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertNotIn('issues:', text)
        self.assertNotIn('push:', text)


if __name__ == '__main__':
    unittest.main()
