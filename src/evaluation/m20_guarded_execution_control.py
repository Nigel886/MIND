"""One owned handle-relative capability for Generation-v2 execution controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from src.evaluation.m20_destination_guard import M20DestinationGuard, M20DispatchLease
from src.evaluation.m20_harness import M20GuardedEvidenceDestination, M20IntegrityError


class M20GuardedExecutionControlSession:
    """Admitted `.m20_execution_control` directory; never falls back to paths."""
    _LEAVES = frozenset({"financial_ledger.json", "live_budget.json", "physical_dispatch.lock", "m20-dispatch-released"})
    _MAX_BYTES = 1024 * 1024

    def __init__(self, destination: Path, guard: M20DestinationGuard) -> None:
        self.destination, self._guard, self._closed, self._lease = destination, guard, False, None

    @classmethod
    def admit(cls, destination: M20GuardedEvidenceDestination,
              ops_factory: Callable[[], Any]) -> "M20GuardedExecutionControlSession":
        ops = ops_factory()
        return cls(destination.destination, M20DestinationGuard.admit_execution_control(destination.trusted_root, destination.components, ops))

    def _usable(self) -> None:
        if self._closed:
            raise M20IntegrityError("guarded execution-control session is closed")
        self._guard.check_intact()

    def inventory(self) -> tuple[str, ...]:
        self._usable(); names = self._guard.enumerate_ordinary()
        if any(name not in self._LEAVES for name in names):
            raise M20IntegrityError("guarded execution-control directory contains an unexpected artifact")
        return names

    def read_json(self, leaf: str) -> Mapping[str, Any] | None:
        if leaf not in self._LEAVES:
            raise M20IntegrityError("guarded execution-control leaf is invalid")
        self.inventory(); payload = self._guard.read_ordinary(leaf, maximum_bytes=self._MAX_BYTES)
        if payload is None:
            return None
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise M20IntegrityError("guarded execution-control artifact is unreadable") from error
        if not isinstance(value, Mapping):
            raise M20IntegrityError("guarded execution-control artifact is invalid")
        return value

    def replace_json(self, leaf: str, value: Mapping[str, Any]) -> None:
        if leaf not in self._LEAVES or leaf == "physical_dispatch.lock":
            raise M20IntegrityError("guarded execution-control replacement leaf is invalid")
        self.inventory()
        active = self._guard.inspect_dispatch_lease("physical_dispatch.lock")
        if active is None or self._lease is None or active.get("lease_id") != self._lease.lease_id:
            raise M20IntegrityError("guarded execution-control mutation requires owned dispatch lease")
        self._guard.replace_ordinary_atomic(leaf, json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode() + b"\n")

    def acquire_dispatch_lease(self, metadata: dict[str, Any]) -> M20DispatchLease:
        self.inventory(); self._lease = self._guard.acquire_dispatch_lease("physical_dispatch.lock", metadata); return self._lease

    def inspect_dispatch_lease(self) -> Mapping[str, Any] | None:
        self.inventory(); return self._guard.inspect_dispatch_lease("physical_dispatch.lock")

    def release_dispatch_lease(self, lease: M20DispatchLease) -> None:
        self._usable(); self._guard.release_dispatch_lease(lease); self._lease = None

    def close(self) -> None:
        if not self._closed:
            try: self._guard.close()
            finally: self._closed = True
