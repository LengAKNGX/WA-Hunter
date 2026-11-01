import random
import unittest

from wa_hunter import (
    ArrayGenerator, HuntStats, RunResult, coverage_markdown, encode_case, minimize,
    should_log_iteration,
)


class WaHunterTests(unittest.TestCase):
    def test_encode_case(self):
        self.assertEqual(encode_case([3, 1, 4]), "3\n3 1 4\n")

    def test_all_strategies_are_covered_first(self):
        cfg = {
            "min_n": 1,
            "max_n": 8,
            "min_value": -10,
            "max_value": 10,
        }
        generator = ArrayGenerator(cfg, random.Random(7))
        observed = [generator.next_case()[0] for _ in generator.STRATEGIES]
        self.assertEqual(observed, generator.STRATEGIES)

    def test_minimize_deletes_and_shrinks(self):
        result, checks = minimize([8, 4, -99, 7], lambda a: any(x < 0 for x in a))
        self.assertEqual(result, [-1])
        self.assertGreater(checks, 0)

    def test_minimize_keeps_int64_precision(self):
        value = -(2**63)
        result, _ = minimize([value], lambda a: a[0] <= -(2**62), value, 2**63 - 1)
        self.assertEqual(result, [-(2**62)])

    def test_hunt_stats_explain_strategy_coverage(self):
        stats = HuntStats()
        ok = RunResult("ok", "1", "", 0.5)
        timeout = RunResult("timeout", "", "", 10.0)
        stats.record("boundary", [1, 2, 3], ok, timeout)
        text = coverage_markdown(stats, 12.5)
        self.assertIn("Executed cases: 1", text)
        self.assertIn("Generated elements: 3", text)
        self.assertIn("| boundary | 1 |", text)
        self.assertIn("brute 1", text)

    def test_progress_log_keeps_coverage_checkpoints_and_failures(self):
        self.assertTrue(should_log_iteration(1, False, 25))
        self.assertTrue(should_log_iteration(25, False, 25))
        self.assertTrue(should_log_iteration(8, True, 25))
        self.assertFalse(should_log_iteration(8, False, 25))


if __name__ == "__main__":
    unittest.main()
