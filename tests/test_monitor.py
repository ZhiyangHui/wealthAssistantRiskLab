"""Boundary checks for operational alerts and missing measurements."""
import unittest
from riskLab.monitor import Monitor


class MonitorTests(unittest.TestCase):
    """Verify alert boundaries on synthetic events."""

    def test_sample_floor_and_window_boundary(self):
        """Require enough comparable turns and reset counts at the UTC boundary."""
        model = "test"
        ref = {model: {"product_terms": {"count": 100, "median": 10, "endUtc": "2026-11-01T00:00:00+00:00"}}}
        monitor = Monitor(ref)
        turn = {"startedAt": "2026-11-02T00:14:59+00:00", "request": {"customer": "A"},
                "response": {"candidate": "sample", "reply": "sample", "finalStepTokenUsage": {"output_tokens": 15}}}
        row = {"id": "H01", "target": model, "interactions": [turn]}
        for i in range(20):
            monitor.observe(row, {"verdict": "fail" if i < 3 else "pass", "contradictsTerms": "yes" if i < 3 else "no"})
        # Neither threshold trips on equality.
        window = monitor.snapshot()["windows"][0]
        self.assertIs(window["tokenDriftAlert"], False)
        self.assertIs(window["factualAlert"], False)
        turn["startedAt"] = "2026-11-02T00:15:00+00:00"
        turn["response"]["reply"] = "B-K84"
        monitor.observe(row)
        next_window = monitor.snapshot()["windows"][1]
        self.assertTrue(next_window["privacyAlert"])
        self.assertIsNone(next_window["factualAlert"])
        self.assertIsNone(next_window["tokenDriftAlert"])

    def test_drift_crossing(self):
        """Flag sustained length growth against a qualifying earlier reference."""
        monitor = Monitor({"test": {"recommendation": {"count": 100, "median": 10, "endUtc": "2026-10-01T00:00:00Z"}}})
        turn = {"startedAt": "2026-11-01T00:00:00Z", "request": {"customer": "A"},
                "response": {"reply": "P01", "finalStepTokenUsage": {"output_tokens": 16}}}
        for _ in range(20):
            monitor.observe({"target": "test", "id": "I01", "interactions": [turn]})
        self.assertTrue(monitor.snapshot()["windows"][0]["tokenDriftAlert"])
