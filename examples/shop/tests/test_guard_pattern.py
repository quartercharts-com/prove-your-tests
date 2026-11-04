"""A name-pattern guard: 'only refund() writes LEDGER.append'. Reads the source text."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "shop.py"


class PatternGuard(unittest.TestCase):
    def test_only_refund_appends_to_ledger(self):
        tree = ast.parse(SOURCE.read_text())
        for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
            if fn.name == "refund":
                continue
            self.assertNotIn("LEDGER.append", ast.unparse(fn), f"{fn.name} writes the ledger")


if __name__ == "__main__":
    unittest.main()
