from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import unittest

from src.evaluation.m16_formal_execution_lock import (
    FormalExecutionAlreadyActiveError,
    FormalExecutionStaleLockError,
    M16FormalExecutionLock,
    _lock_path,
    recover_stale_lock,
)


class FormalExecutionLockTests(unittest.TestCase):
    def test_first_owner_acquires_and_clean_shutdown_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "restart1"
            lock = M16FormalExecutionLock(directory, "manifest")
            with lock:
                self.assertTrue(lock.path.exists())
            self.assertFalse(lock.path.exists())
            with M16FormalExecutionLock(directory, "manifest"):
                pass

    def test_second_owner_is_rejected_before_any_fake_provider_work(self) -> None:
        provider_calls = 0
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "restart1"
            with M16FormalExecutionLock(directory, "manifest"):
                with self.assertRaises(FormalExecutionAlreadyActiveError):
                    M16FormalExecutionLock(directory, "manifest").acquire()
                self.assertEqual(provider_calls, 0)
                self.assertFalse(directory.exists())

    def test_different_namespaces_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with M16FormalExecutionLock(root / "one", "manifest"), M16FormalExecutionLock(root / "two", "manifest"):
                pass

    def test_live_lock_is_not_recovered_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "restart1"
            with M16FormalExecutionLock(directory, "manifest"):
                with self.assertRaises(FormalExecutionStaleLockError):
                    recover_stale_lock(directory, "manifest")

    def test_explicit_verified_stale_recovery_archives_not_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "restart1"
            path = _lock_path(directory, "manifest")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "result_directory": str(directory.resolve()).casefold(), "manifest_hash": "manifest",
                "hostname": socket.gethostname(), "pid": 99999999, "process_start_identity": "dead", "owner_nonce": "stale",
            }), encoding="utf-8")
            archived = recover_stale_lock(directory, "manifest")
            self.assertTrue(archived.exists())
            self.assertFalse(path.exists())
