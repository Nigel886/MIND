"""Test-only identity-keyed NativeDestinationOps model; it never touches Host paths."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import count
from src.evaluation.m20_destination_guard import M20DestinationIdentity, M20DestinationGuardViolation, M20DirectoryEntry


@dataclass
class _Node:
    directory: bool
    reparse: bool = False
    data: bytes = b""
    children: dict[str, int] | None = None


class MemoryNativeOps:
    """Opaque handles resolve names only through retained identity-keyed parents."""
    def __init__(self) -> None:
        self._ids = count(1); self.nodes: dict[int, _Node] = {}; self.handles: dict[int, int] = {}
        self.closed: list[int] = []; self.fail: dict[str, BaseException] = {}; self.root = self.mkdir_node()
        self.enumeration_override: tuple[M20DirectoryEntry, ...] | None = None
        self.on_enumerate = None

    def mkdir_node(self, *, reparse: bool = False) -> int:
        ident = next(self._ids); self.nodes[ident] = _Node(True, reparse, children={}); return ident
    def file_node(self, data: bytes = b"", *, reparse: bool = False) -> int:
        ident = next(self._ids); self.nodes[ident] = _Node(False, reparse, data); return ident
    def provision(self, parent: int, name: str, *, directory: bool = True, reparse: bool = False, data: bytes = b"") -> int:
        node = self.mkdir_node(reparse=reparse) if directory else self.file_node(data, reparse=reparse)
        self.nodes[parent].children[name] = node; return node
    def substitute(self, parent: int, name: str, replacement: int) -> None: self.nodes[parent].children[name] = replacement
    def _maybe(self, name: str) -> None:
        if name in self.fail: raise self.fail[name]
    def _handle(self, node: int) -> int:
        handle = next(self._ids); self.handles[handle] = node; return handle
    def _node(self, handle: int) -> _Node:
        if handle not in self.handles: raise M20DestinationGuardViolation("invalid synthetic handle")
        return self.nodes[self.handles[handle]]
    def open_trusted_root(self, _path: str) -> int: self._maybe("admit"); return self._handle(self.root)
    def open_relative_directory(self, parent_handle: int, component: str) -> int:
        self._maybe("directory"); parent=self._node(parent_handle); child=parent.children.get(component) if parent.children else None
        if child is None: raise FileNotFoundError(component)
        return self._handle(child)
    def identity(self, handle: int) -> M20DestinationIdentity:
        node=self._node(handle); ident=self.handles[handle].to_bytes(16,"big")
        return M20DestinationIdentity(1, ident, node.directory, node.reparse)
    def close(self, handle: int) -> None:
        self._maybe("close"); self.handles.pop(handle, None); self.closed.append(handle)
    def create_exclusive(self, parent_handle: int, leaf: str) -> int:
        self._maybe("create"); parent=self._node(parent_handle)
        if not parent.directory or leaf in parent.children: raise FileExistsError(leaf)
        child=self.file_node(); parent.children[leaf]=child; return self._handle(child)
    def write_flush(self, handle: int, data: bytes) -> None:
        self._maybe("write"); self._node(handle).data=data; self._maybe("flush")
    def open_relative_file_readonly(self, parent_handle: int, leaf: str) -> int:
        parent=self._node(parent_handle); child=parent.children.get(leaf) if parent.children else None
        if child is None: raise FileNotFoundError(leaf)
        return self._handle(child)
    def open_relative_file(self, parent_handle: int, leaf: str) -> int: return self.open_relative_file_readonly(parent_handle, leaf)
    def read_file(self, handle: int, maximum: int) -> bytes:
        self._maybe("read"); data=self._node(handle).data
        if len(data)>maximum: raise M20DestinationGuardViolation("oversize")
        return data
    def enumerate_relative_directory(self, parent_handle: int, *, maximum_entries: int,
                                     maximum_name_bytes: int,
                                     maximum_entry_name_bytes: int) -> tuple[M20DirectoryEntry, ...]:
        self._maybe("enumerate"); parent=self._node(parent_handle)
        if not parent.directory: raise M20DestinationGuardViolation("synthetic enumeration parent is not a directory")
        if self.enumeration_override is not None:
            entries = self.enumeration_override
        else:
            entries = tuple(M20DirectoryEntry(name, len(name.encode("utf-16-le")), node.directory, node.reparse)
                for name, ident in parent.children.items() for node in (self.nodes[ident],))
        result=[]; total=0
        for index, entry in enumerate(entries):
            if index and "enumerate_mid" in self.fail: raise self.fail["enumerate_mid"]
            result.append(entry); total += entry.name_bytes
            if len(result)>maximum_entries or entry.name_bytes>maximum_entry_name_bytes or total>maximum_name_bytes:
                raise M20DestinationGuardViolation("synthetic directory inventory exceeds bounds")
        if callable(self.on_enumerate): self.on_enumerate()
        return tuple(result)
    def rename_relative(self, parent_handle: int, source: str, target: str, *, replace_existing: bool) -> None:
        self._maybe("replace"); parent=self._node(parent_handle)
        if source not in parent.children: raise FileNotFoundError(source)
        if target in parent.children and not replace_existing: raise FileExistsError(target)
        parent.children[target]=parent.children.pop(source)
    def rename_open_file(self, handle: int, parent_handle: int, target: str, *, replace_existing: bool) -> None:
        parent=self._node(parent_handle); node=self.handles[handle]
        source=next((name for name,value in parent.children.items() if value==node), None)
        if source is None: raise FileNotFoundError(target)
        self.rename_relative(parent_handle,source,target,replace_existing=replace_existing)
    def bytes_at(self, parent: int, leaf: str) -> bytes: return self.nodes[self.nodes[parent].children[leaf]].data
    def factory(self, trusted_root, destination, components=("evidence",)):
        """Build the real production factory over this in-memory NativeOps boundary."""
        from src.evaluation.m20_harness import M20GuardedEvidenceDestination, M20GuardedEvidenceWriterFactory
        return M20GuardedEvidenceWriterFactory(M20GuardedEvidenceDestination(str(trusted_root), tuple(components), destination), ops_factory=lambda: self)
    def store_access_provider(self, trusted_root, destination, components=("evidence",)):
        from src.evaluation.m20_harness import M20GuardedEvidenceDestination, M20GuardedEvidenceStoreAccessProvider
        return M20GuardedEvidenceStoreAccessProvider(M20GuardedEvidenceDestination(str(trusted_root), tuple(components), destination), ops_factory=lambda: self)
