from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControllerDispatchTests(unittest.TestCase):
    def test_controller_is_owner_only_and_allowlisted(self):
        text = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertIn('types: [opened, reopened]', text)
        self.assertIn('github.event.issue.user.login == github.repository_owner', text)
        self.assertIn('actions: write', text)
        self.assertIn('public-compute.yml/dispatches', text)
        self.assertIn("-f ref='cloud-workspace-v1'", text)
        for profile in ('runtime-smoke', 'handoff-verify-v1', 'risk-v2-severity-persistence-v1'):
            self.assertIn(f'controller: {profile}', text)
            self.assertIn(f"profile='{profile}'", text)

    def test_reopen_is_bounded_to_existing_v0800_f_controller_issue(self):
        text = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertIn("github.event.action == 'opened' ||", text)
        self.assertIn("github.event.action == 'reopened'", text)
        self.assertIn('github.event.issue.number == 227', text)
        self.assertIn("github.event.issue.title == 'controller: two-wave-v0800-f-operational-state-stream-audit-v1'", text)
        self.assertEqual(text.count("github.event.issue.number == 227"), 1)
        self.assertEqual(text.count("github.event.action == 'reopened'"), 1)

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
