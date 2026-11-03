import unittest

from riskLab.__main__ import run_case
from riskLab.cases import cases


class HarnessTests(unittest.TestCase):
    """Check evidence and status decisions for the offline harness."""
    def run_one(self, case_id, target=None):
        """Run the first variant of a case with an optional target."""
        case = next(c for c in cases() if c.id == case_id)
        return run_case(case, target, "test", "test-double")

    def test_probe_does_not_count_as_an_assistant_result(self):
        """Keep direct tool verdicts separate from unobserved model behaviour."""
        self.assertEqual(self.run_one("T01")["status"], "passed")
        row = self.run_one("T02")
        self.assertEqual(row["toolProbe"]["events"][0]["result"], {"allowed": False})
        row = self.run_one("T03")
        self.assertTrue(row["toolProbe"]["passed"])
        self.assertEqual(row["status"], "awaiting_target")

    def test_cross_session_marker_requires_two_distinct_sessions(self):
        """Check cross-session disclosure and the priming precondition."""
        def leaky_target(request, call):
            """Simulate a target that discloses the private marker."""
            call("holdings")
            return {"reply": "Holding B-K84"}
        row = self.run_one("D02", leaky_target)
        self.assertEqual(row["status"], "failed")
        b, a = row["interactions"]
        self.assertNotEqual(b["request"]["sessionId"], a["request"]["sessionId"])
        self.assertEqual([t["toolCalls"][0]["result"]["owner"] for t in (b, a)], ["B", "A"])
        unprimed = self.run_one("D02", lambda request, call: {"reply": "No holdings."})
        self.assertEqual(unprimed["status"], "inconclusive")

    def test_target_error_preserves_prior_calls(self):
        """Keep completed tool calls when the target fails."""
        def broken_target(request, call):
            """Raise an error after a denied tool request."""
            call("riskProfile", "B")
            raise RuntimeError("test error")
        row = self.run_one("D01", broken_target)
        self.assertEqual(row["status"], "inconclusive")
        self.assertFalse(row["interactions"][0]["toolCalls"][0]["result"]["allowed"])

    def test_clean_and_injected_briefs_share_business_prompt(self):
        """Change only the external brief in each indirect attack."""
        group = [c for c in cases() if c.id == "I02"]
        self.assertEqual(len(group), 4)
        clean = group[0]
        for changed in group[1:]:
            self.assertEqual(changed.prompt, clean.prompt)
            self.assertEqual(changed.control, "I02/clean")
            self.assertEqual([line for line in changed.brief.splitlines() if line in clean.brief.splitlines()],
                             clean.brief.splitlines())
