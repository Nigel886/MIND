"""Controlled local tool contracts for M8."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from types import MappingProxyType
from src.core.observation import Observation

def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value): raise TypeError("mapping keys must be strings")
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)): return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)): return frozenset(_freeze(v) for v in value)
    return deepcopy(value)
def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping): return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple): return [_thaw(v) for v in value]
    if isinstance(value, frozenset): return sorted((_thaw(v) for v in value), key=repr)
    return deepcopy(value)
def _name(value: Any) -> None:
    if not isinstance(value, str): raise TypeError("tool name must be a str")
    if not value.strip(): raise ValueError("tool name must not be empty")

_PRIVATE_DESCRIPTOR_KEYS = frozenset({"expected_answer", "ground_truth", "correct_tool", "correct_action", "completion_label", "evaluator_success"})

def _json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)): return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")): raise ValueError("JSON floats must be finite")
        return value
    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            if not isinstance(key, str): raise TypeError("JSON mapping keys must be strings")
            if key in _PRIVATE_DESCRIPTOR_KEYS: raise ValueError("private evaluator field is forbidden")
            output[key] = _json(item)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)): return tuple(_json(item) for item in value)
    raise TypeError("value must be JSON-compatible")

@dataclass(frozen=True)
class CapabilityDescriptor:
    """Immutable public capability information derived from a registered tool."""
    tool_id: str
    display_name: str | None = None
    description: str | None = None
    parameter_schema: dict[str, Any] | None = None
    def __post_init__(self) -> None:
        _name(self.tool_id)
        if self.display_name is not None and (not isinstance(self.display_name, str) or not self.display_name.strip()): raise ValueError("display_name must be non-empty when present")
        if self.description is not None and not isinstance(self.description, str): raise TypeError("description must be a string or None")
        if self.parameter_schema is not None and not isinstance(self.parameter_schema, dict): raise TypeError("parameter_schema must be a dict or None")
        object.__setattr__(self, "parameter_schema", _json(self.parameter_schema) if self.parameter_schema is not None else None)
    def to_dict(self) -> dict[str, Any]: return {"tool_id": self.tool_id, "display_name": self.display_name, "description": self.description, "parameter_schema": _thaw(self.parameter_schema)}
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityDescriptor":
        if not isinstance(data, dict): raise TypeError("CapabilityDescriptor data must be a dict")
        return cls(data["tool_id"], data.get("display_name"), data.get("description"), data.get("parameter_schema"))

class Tool(Protocol):
    @property
    def name(self) -> str: ...
    def execute(self, parameters: dict[str, Any]) -> "ToolResult": ...

@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    output: Any | None
    error: str | None
    parameters: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        _name(self.tool_name)
        if not isinstance(self.success, bool): raise TypeError("success must be a bool")
        if self.error is not None and not isinstance(self.error, str): raise TypeError("error must be a str or None")
        if self.error is not None and not self.error.strip(): raise ValueError("error must not be empty")
        if self.success and self.error is not None: raise ValueError("successful result must not have error")
        if not self.success and (self.output is not None or self.error is None): raise ValueError("failed result requires error and no output")
        if not isinstance(self.parameters, dict) or not isinstance(self.metadata, dict): raise TypeError("parameters and metadata must be dicts")
        object.__setattr__(self, "output", _freeze(self.output)); object.__setattr__(self, "parameters", _freeze(self.parameters)); object.__setattr__(self, "metadata", _freeze(self.metadata))
    def to_dict(self) -> dict[str, Any]: return {"tool_name": self.tool_name, "success": self.success, "output": _thaw(self.output), "error": self.error, "parameters": _thaw(self.parameters), "metadata": _thaw(self.metadata)}
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResult":
        if not isinstance(data, dict): raise TypeError("ToolResult data must be a dict")
        return cls(data["tool_name"], data["success"], data["output"], data["error"], data["parameters"], data["metadata"])

class ToolRegistry:
    def __init__(self) -> None: self._tools: dict[str, Tool] = {}
    def register(self, tool: Tool) -> None:
        if not hasattr(tool, "name") or not callable(getattr(tool, "execute", None)): raise TypeError("tool must expose name and execute")
        _name(tool.name)
        if tool.name in self._tools: raise ValueError("duplicate tool name")
        self._tools[tool.name] = tool
    def get(self, name: str) -> Tool:
        _name(name)
        if name not in self._tools: raise LookupError(f"unknown tool: {name}")
        return self._tools[name]
    def contains(self, name: str) -> bool: _name(name); return name in self._tools
    def list_names(self) -> tuple[str, ...]: return tuple(self._tools)
    def capability_descriptors(self) -> tuple[CapabilityDescriptor, ...]:
        """Return public descriptors derived only from registered tool attributes."""
        output = []
        for name, tool in self._tools.items():
            output.append(CapabilityDescriptor(name, getattr(tool, "display_name", None), getattr(tool, "description", None), getattr(tool, "parameter_schema", None)))
        return tuple(output)
    def validate_call(self, name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Registry admission: reject unknown tools and validate declared public schema."""
        tool = self.get(name)
        if not isinstance(parameters, dict): raise TypeError("tool parameters must be a dict")
        frozen = _json(parameters); schema = getattr(tool, "parameter_schema", None)
        if schema is not None:
            if not isinstance(schema, dict): raise TypeError("tool parameter_schema must be a dict")
            required = schema.get("required", ())
            if not isinstance(required, (list, tuple)) or any(not isinstance(k, str) for k in required): raise ValueError("invalid required parameter schema")
            if any(key not in frozen for key in required): raise ValueError("missing required tool parameter")
            properties = schema.get("properties")
            if schema.get("additionalProperties") is False and isinstance(properties, dict) and any(key not in properties for key in frozen): raise ValueError("unknown tool parameter")
        return _thaw(frozen)

def tool_result_to_observation(result: ToolResult) -> Observation:
    if not isinstance(result, ToolResult): raise TypeError("result must be a ToolResult")
    data = result.to_dict()
    return Observation(source=f"tool:{result.tool_name}", content=data)
