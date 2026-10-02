import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import app


class OracleValidationTests(unittest.TestCase):
    def test_accepts_bounded_cpp_oracle(self):
        result = app.validate_oracle({
            "supported": True,
            "reason": "simple reference",
            "brute_cpp": "#include <iostream>\nint main(){int n;std::cin>>n;std::cout<<n;}",
            "min_n": 1,
            "max_n": 10,
            "min_value": -5,
            "max_value": 5,
            "assumptions": ["single case"],
            "review_notes": "check output semantics",
        })
        self.assertEqual(result["max_n"], 10)
        self.assertIn("single case", result["notes"])

    def test_rejects_unsupported_problem(self):
        with self.assertRaisesRegex(RuntimeError, "暂不支持"):
            app.validate_oracle({"supported": False, "reason": "graph input"})

    def test_rejects_system_calls(self):
        with self.assertRaisesRegex(RuntimeError, "禁止"):
            app.validate_oracle({
                "supported": True,
                "brute_cpp": "int main(){system(\"id\");}",
                "min_n": 1, "max_n": 2, "min_value": 0, "max_value": 1,
            })


if __name__ == "__main__":
    unittest.main()
