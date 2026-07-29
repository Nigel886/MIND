"""Safe deterministic CalculatorTool."""
from __future__ import annotations
from math import isfinite
from typing import Any
from src.core.tool import ToolResult
class CalculatorTool:
    name = "calculator"
    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        if not isinstance(parameters, dict): raise TypeError("parameters must be a dict")
        if set(parameters) != {"operation", "operands"}: raise ValueError("parameters must contain only operation and operands")
        operation, operands = parameters["operation"], parameters["operands"]
        if not isinstance(operation, str): raise TypeError("operation must be a str")
        if operation not in ("add", "multiply"): raise ValueError("unsupported operation")
        if not isinstance(operands, (list, tuple)): raise TypeError("operands must be a list or tuple")
        if len(operands) != 2: raise ValueError("exactly two operands are required")
        for value in operands:
            if isinstance(value, bool) or not isinstance(value, (int, float)): raise TypeError("operands must be int or float, not bool")
            if isinstance(value, float) and not isfinite(value): raise ValueError("operands must be finite")
        output = operands[0] + operands[1] if operation == "add" else operands[0] * operands[1]
        return ToolResult(self.name, True, output, None, parameters)
