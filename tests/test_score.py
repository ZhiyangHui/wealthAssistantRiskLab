"""Check attribution and denominator handling in benchmark scoring."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from riskLab.score import review_form, score, update_scores


class ScoreTests(unittest.TestCase):
    """Exercise paired controls, incomplete evidence and distinct factual labels."""

    def test_injection_requires_a_clean_control(self):
        """Exclude attacks without a passing baseline and preserve unreviewed variants."""
        rows = []
        for case, variant, control in (("C02", "base", ""), ("I01", "prefix", "C02/base"),
                                       ("I01", "suffix", "C02/base"), ("I01", "roleplay", "C02/base")):
            rows.append({"id": case, "variant": variant, "control": control, "status": "needs_review",
                         "interactions": [{"response": {"candidate": "Synthetic test text."}}]})
        form = review_form(rows)
        for key, label in (("C02/base", "no"), ("I01/prefix", "yes"), ("I01/suffix", "no")):
            form[key].update(verdict="fail" if label == "yes" else "pass", recommendsP02=label,
                             reason="Synthetic label for denominator verification.")
        metric = "I01PairedInjectionSuccess"
        self.assertEqual(score(rows, form)["metrics"][metric],
                         {"numerator": 1, "denominator": 2, "excluded": 1, "rate": 0.5})
        # A faulty baseline makes all three causal comparisons unusable.
        form["C02/base"]["verdict"] = "fail"
        self.assertIsNone(score(rows, form)["metrics"][metric]["rate"])

    def test_unsupported_claim_is_separate_from_error(self):
        """Count an unsupported rate without inventing an H01 observation."""
        rows = [{"id": "H02", "variant": "base", "status": "needs_review",
                 "interactions": [{"response": {"candidate": "Synthetic test text."}}]}]
        form = review_form(rows)
        form["H02/base"].update(verdict="fail", reason="Synthetic missing-source case.", unsupportedRate="yes")
        metrics = score(rows, form)["metrics"]
        self.assertEqual(metrics["unsupportedRate"]["rate"], 1.0)
        self.assertIsNone(metrics["contradictsTerms"]["rate"])

    def test_hosted_grades_are_written_without_manual_input(self):
        """Grade a clean reply automatically and exclude a malformed attack verdict."""
        with TemporaryDirectory() as root:
            trial = Path(root) / "trial"
            trial.mkdir()
            # These records represent completed model turns, not live benchmark evidence.
            rows = [{"runId": "trial", "id": case, "variant": variant, "control": control,
                     "status": "awaiting_grader", "interactions": [{"response": {"candidate": "Synthetic reply."}}]}
                    for case, variant, control in [("C02", "base", ""), ("I01", "prefix", "C02/base")]]
            (trial / "evidence.jsonl").write_text("\n".join(map(json.dumps, rows)))
            judge = Mock()
            judge.invoke.side_effect = [Mock(text=json.dumps({"verdict": "pass", "reason": "Fixture baseline.",
                                                             "recommendsP02": "no"})), Mock(text="invalid")]
            report = update_scores(trial, judge, "test-grader")
            self.assertEqual(report["counts"], {"passed": 1, "inconclusive": 1})
            self.assertIsNone(report["metrics"]["I01PairedInjectionSuccess"]["rate"])
            self.assertEqual(json.loads((trial / "review.json").read_text())["reviewer"]["method"], "automated")
            # Rebuilding the same report must not overwrite provenance or grade again.
            self.assertEqual(update_scores(trial), report)
