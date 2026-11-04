"""Verify end-to-end containment, delayed evidence and private incident records."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from riskLab.assistant import FALLBACK, ReleaseGate
from riskLab.bank import BankSession
from riskLab.containment import CircuitBreaker
from riskLab.manage import run_checks
from riskLab.monitor import Monitor


class ContainmentTests(unittest.TestCase):
    """Exercise actual release paths without a hosted model or API credentials."""

    def request(self, number=0):
        """Build a distinct authenticated request for a factual question.

        Args:
            number: Unique session suffix within the test.

        Returns:
            Synthetic request accepted by the release gate.
        """
        return {"customer": "A", "caseId": "H01", "sessionId": f"session-{number}",
                "prompt": "Explain the terms.", "thirdPartyBrief": ""}

    def test_scripted_suite_and_saved_evidence(self):
        """Require every reported pass to have observable control evidence."""
        with TemporaryDirectory() as root:
            report, path = run_checks(Path(root))
            self.assertEqual(report["passed"], report["total"])
            saved = Path(root) / "partB" / report["runId"] / "checks.json"
            self.assertEqual(json.loads(saved.read_text()), report)
            self.assertIn("7/7", path.read_text())
            # Persistence must not copy the scripted private candidate or session ID.
            control = saved.parent / "B01" / "control.json"
            self.assertEqual(control.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("B-K84", control.read_text())
            self.assertNotIn("scripted-session", control.read_text())

    def test_delayed_grades_trip_without_double_counting(self):
        """Latch on a corrected fourth error and preserve previously received grades."""
        gate = ReleaseGate(None)
        fixed = datetime(2026, 11, 2, tzinfo=timezone.utc)
        with patch("riskLab.assistant.datetime") as clock, patch(
                "riskLab.assistant.draft", return_value={"candidate": "Scripted terms"}) as generate:
            clock.now.return_value = fixed
            for index in range(20):
                gate.respond(self.request(index), BankSession("A").call)
            grades = {f"session-{i}": {"verdict": "fail" if i < 3 else "pass",
                                      "contradictsTerms": "yes" if i < 3 else "no"} for i in range(20)}
            gate.apply_assessments(grades)
            self.assertFalse(gate.breaker.is_open)
            # A delayed correction changes the original window instead of adding traffic.
            gate.apply_assessments({"session-3": {"verdict": "fail", "contradictsTerms": "yes"}})
            window = gate.monitor.snapshot()["windows"][0]
            self.assertEqual((window["requests"], window["factualScored"], window["contradictions"]), (20, 20, 4))
            self.assertTrue(gate.breaker.is_open)
            result = gate.respond(self.request(20), BankSession("A").call)
            self.assertEqual(result["reply"], FALLBACK)
            self.assertEqual(generate.call_count, 20)
            # Even a later correction cannot reopen the service without operational review.
            gate.apply_assessments({"session-3": {"verdict": "pass", "contradictsTerms": "no"}})
            self.assertTrue(gate.breaker.is_open)

    def test_live_token_counts_stop_next_generation(self):
        """Connect actual gate measurements to the next request's fallback route."""
        baseline = {"scripted": {"product_terms": {"count": 100, "median": 100,
                                                   "endUtc": "2026-11-01T00:00:00Z"}}}
        gate = ReleaseGate(None, monitor=Monitor(baseline), target="scripted")
        fixed = datetime(2026, 11, 2, tzinfo=timezone.utc)
        with patch("riskLab.assistant.datetime") as clock, patch("riskLab.assistant.draft", return_value={
                "candidate": "Scripted terms", "finalStepTokenUsage": {"output_tokens": 160}}) as generate:
            clock.now.return_value = fixed
            for index in range(19):
                gate.respond(self.request(index), BankSession("A").call)
            self.assertFalse(gate.breaker.is_open)
            gate.respond(self.request(19), BankSession("A").call)
            self.assertTrue(gate.breaker.is_open)
            clock.now.return_value = datetime(2026, 11, 2, 0, 15, tzinfo=timezone.utc)
            later = gate.respond(self.request(20), BankSession("A").call)
            self.assertEqual(later["route"], "circuit_open")
            self.assertEqual(generate.call_count, 20)

    def test_corrupt_state_prevents_startup(self):
        """Refuse to start instead of silently clearing unreadable incident state."""
        with TemporaryDirectory() as root:
            path = Path(root) / "control.json"
            path.write_text("{broken")
            with self.assertRaises(ValueError):
                CircuitBreaker(root)
            # Parseable but inconsistent state is also unsafe to treat as a fresh service.
            path.write_text(json.dumps({"open": False, "incident": {"id": "unresolved"}, "handoffs": []}))
            with self.assertRaises(ValueError):
                CircuitBreaker(root)

    def test_persistence_failure_does_not_release_private_draft(self):
        """Keep the in-memory latch open if writing the incident record fails."""
        gate = ReleaseGate(None)
        with patch("riskLab.assistant.draft", return_value={"candidate": "B-K84"}), patch.object(
                gate.breaker, "_save", side_effect=OSError("Scripted storage failure")):
            with self.assertRaises(OSError):
                gate.respond(self.request(), BankSession("A").call)
        self.assertTrue(gate.breaker.is_open)
