import random
import unittest

from wa_hunter import ArrayGenerator, encode_case, minimize


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


if __name__ == "__main__":
    unittest.main()
