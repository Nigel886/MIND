import unittest
from decimal import Decimal
from src.tools.calculator import CalculatorTool
class CalculatorToolTest(unittest.TestCase):
    def setUp(self): self.tool = CalculatorTool()
    def test_operations(self):
        self.assertEqual(self.tool.execute({"operation":"add","operands":[17,23]}).output, 40)
        self.assertEqual(self.tool.execute({"operation":"multiply","operands":[17,23]}).output, 391)
        self.assertEqual(self.tool.execute({"operation":"add","operands":[1.5,2]}).output, 3.5)
    def test_invalid_inputs(self):
        for value in (True, "1", Decimal("1"), complex(1,1), float("nan"), float("inf")):
            with self.assertRaises((TypeError, ValueError)): self.tool.execute({"operation":"add","operands":[value, 2]})
        with self.assertRaises(ValueError): self.tool.execute({"operation":"divide","operands":[1,2]})
        with self.assertRaises(ValueError): self.tool.execute({"operation":"add","operands":[1]})
        with self.assertRaises(ValueError): self.tool.execute({"operation":"add","operands":[1,2],"x":1})
