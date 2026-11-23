"""Native-free coverage for the isolated M20 Guard evidence-writer candidate."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.evaluation.m20_harness import (GuardedEvidenceWriter, M20EvidenceStore, M20IntegrityError,
                         M20LifecycleState, M20Namespace, M20ResourceTelemetry, M20_RECORD_SCHEMA)
from src.evaluation.m20_prospective_feasibility import M20ProspectiveFeasibilityRunner
from src.evaluation.m20_destination_guard import M20DestinationGuardViolation


class _Identity:
    def __init__(self, *, directory: bool = False, reparse: bool = False) -> None:
        self.is_directory, self.is_reparse_point = directory, reparse


class _Guard:
    def __init__(self, *, create_error: BaseException | None = None,
                 write_error: BaseException | None = None,
                 rename_error: BaseException | None = None) -> None:
        self.create_error, self.write_error, self.rename_error = create_error, write_error, rename_error
        self.created: list[str] = []
        self.writes: list[tuple[object, bytes]] = []
        self.renames: list[tuple[str, str, bool]] = []
        self.closed_handles: list[object] = []
        self.closed = 0

    def create_exclusive(self, name: str) -> object:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(name)
        return object()

    def write_flush(self, handle: object, payload: bytes) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.writes.append((handle, payload))

    def rename_relative(self, source: str, target: str, *, replace_existing: bool) -> None:
        if self.rename_error is not None:
            raise self.rename_error
        self.renames.append((source, target, replace_existing))

    def close(self) -> None:
        self.closed += 1


class _RecordingWriter:
    def __init__(self, destination: Path, *, fail: BaseException | None = None) -> None:
        self.destination, self.fail = destination, fail
        self.writes: list[tuple[str, bytes]] = []
        self.renames: list[tuple[str, str]] = []
        self.closed = 0

    def write_new_atomic(self, leaf_name: str, payload: bytes) -> None:
        if self.fail is not None:
            raise self.fail
        self.writes.append((leaf_name, payload))

    def rename_no_replace(self, source_name: str, target_name: str) -> None:
        self.renames.append((source_name, target_name))

    def validate_and_rename_no_replace(self, source_name: str, target_name: str, validator) -> None:
        validator((self.destination / source_name).read_bytes())
        self.renames.append((source_name, target_name))

    def close(self) -> None:
        self.closed += 1


class GuardedEvidenceWriterTests(unittest.TestCase):
    def _writer(self, guard: _Guard, *, identity: _Identity | None = None) -> GuardedEvidenceWriter:
        return GuardedEvidenceWriter(Path(r"C:\offline-evidence"), guard,
                                     identity=lambda _handle: identity or _Identity(),
                                     close_handle=guard.closed_handles.append)

    def test_guarded_write_verifies_identity_flushes_and_renames_without_replace(self) -> None:
        guard = _Guard()
        writer = self._writer(guard)
        writer.write_new_atomic("manifest.json", b"payload")
        self.assertEqual(len(guard.created), 1)
        self.assertTrue(guard.created[0].endswith(".tmp"))
        self.assertEqual(guard.writes[0][1], b"payload")
        self.assertEqual(guard.renames, [(guard.created[0], "manifest.json", False)])
        self.assertEqual(len(guard.closed_handles), 1)
        writer.close(); writer.close()
        self.assertEqual(guard.closed, 1)

    def test_collision_rejection_preserves_temporary_and_latches_fail_closed(self) -> None:
        guard = _Guard(rename_error=FileExistsError("completed evidence already exists"))
        writer = self._writer(guard)
        with self.assertRaises(FileExistsError):
            writer.write_new_atomic("record.json", b"payload")
        self.assertEqual(len(guard.created), 1)
        self.assertEqual(len(guard.closed_handles), 1)
        self.assertEqual(guard.renames, [])
        with self.assertRaisesRegex(M20IntegrityError, "fail-closed"):
            writer.write_new_atomic("other.json", b"other")

    def test_guard_invalidation_and_reparse_identity_fail_closed_before_write(self) -> None:
        invalid = self._writer(_Guard(create_error=M20DestinationGuardViolation("identity changed")))
        with self.assertRaises(M20DestinationGuardViolation):
            invalid.write_new_atomic("record.json", b"payload")
        guard = _Guard()
        reparse = self._writer(guard, identity=_Identity(reparse=True))
        with self.assertRaisesRegex(M20IntegrityError, "ordinary file"):
            reparse.write_new_atomic("record.json", b"payload")
        self.assertEqual(guard.writes, [])
        self.assertEqual(guard.renames, [])
        self.assertEqual(len(guard.closed_handles), 1)

    def test_failure_after_temporary_creation_closes_once_and_never_renames(self) -> None:
        guard = _Guard(write_error=M20DestinationGuardViolation("WriteFile failed"))
        writer = self._writer(guard)
        with self.assertRaises(M20DestinationGuardViolation):
            writer.write_new_atomic("record.json", b"payload")
        self.assertEqual(len(guard.created), 1)
        self.assertEqual(len(guard.closed_handles), 1)
        self.assertEqual(guard.renames, [])

    def test_close_failure_also_latches_fail_closed_before_rename(self) -> None:
        guard = _Guard()
        def close_error(_handle: object) -> None:
            raise M20DestinationGuardViolation("CloseHandle failed")
        writer = GuardedEvidenceWriter(Path(r"C:\offline-evidence"), guard,
                                       identity=lambda _handle: _Identity(), close_handle=close_error)
        with self.assertRaises(M20DestinationGuardViolation):
            writer.write_new_atomic("record.json", b"payload")
        self.assertEqual(guard.renames, [])
        with self.assertRaisesRegex(M20IntegrityError, "fail-closed"):
            writer.write_new_atomic("other.json", b"payload")

    def test_store_uses_injected_writer_without_path_fallback_and_resolves_partial_without_replace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); root.mkdir(exist_ok=True)
            writer = _RecordingWriter(root)
            manifest = SimpleNamespace(digest="manifest-digest")
            store = M20EvidenceStore(root, manifest, M20Namespace.FAKE, writer=writer)
            self.assertEqual(writer.writes[0][0], "manifest.json")
            execution_id = "a" * 64
            partial = root / (execution_id + ".partial.json")
            partial.write_text(json.dumps({"lifecycle": M20LifecycleState.ZERO_COMMIT_PARTIAL.value,
                                           "execution_id": execution_id, "spec": execution_id,
                                           "telemetry": {}}), encoding="utf-8")
            spec = SimpleNamespace(namespace=M20Namespace.FAKE, manifest_digest="manifest-digest",
                                   execution_id=execution_id)
            store.resume_partial(spec)
            self.assertEqual(writer.renames, [(partial.name, execution_id + ".partial.resolved.json")])
            self.assertTrue(partial.exists())  # Fixture remains: writer alone owns the rename.
            store.close(); self.assertEqual(writer.closed, 1)

    def test_store_does_not_fallback_when_guarded_marker_write_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); root.mkdir(exist_ok=True)
            writer = _RecordingWriter(root, fail=M20DestinationGuardViolation("unsupported"))
            with self.assertRaises(M20DestinationGuardViolation):
                M20EvidenceStore(root, SimpleNamespace(digest="manifest-digest"), M20Namespace.FAKE,
                                 writer=writer)
            self.assertFalse((root / "manifest.json").exists())
            self.assertEqual(writer.closed, 1)

    def test_persist_routes_completed_record_to_guarded_atomic_writer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); root.mkdir(exist_ok=True)
            writer = _RecordingWriter(root)
            manifest = SimpleNamespace(digest="manifest-digest")
            store = M20EvidenceStore(root, manifest, M20Namespace.FAKE, writer=writer)
            execution_id = "b" * 64
            spec = SimpleNamespace(namespace=M20Namespace.FAKE, manifest_digest="manifest-digest",
                                   execution_id=execution_id)
            record = SimpleNamespace(spec=spec, execution_id=execution_id, schema=M20_RECORD_SCHEMA,
                                     provenance={"source": "offline-test"}, digest="record-digest",
                                     canonical=lambda: {"execution_id": execution_id})
            store.persist(record)
            leaf, payload = writer.writes[-1]
            self.assertEqual(leaf, execution_id + ".json")
            self.assertEqual(json.loads(payload), {"digest": "record-digest", "execution_id": execution_id})

    def test_prospective_store_factory_is_explicit_and_offline(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); root.mkdir(exist_ok=True)
            supplied: list[_RecordingWriter] = []
            def factory(destination: Path) -> _RecordingWriter:
                writer = _RecordingWriter(destination)
                supplied.append(writer)
                return writer
            runner = M20ProspectiveFeasibilityRunner(evidence_writer_factory=factory)
            store = runner.store(root)
            self.assertEqual(len(supplied), 1)
            self.assertEqual(supplied[0].writes[0][0], "manifest.json")
            store.close()
            self.assertEqual(supplied[0].closed, 1)


if __name__ == "__main__":
    unittest.main()
