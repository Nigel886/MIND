"""Host-static regression coverage for the Windows control-directory bridge."""
from __future__ import annotations

import unittest

from src.evaluation.m20_destination_guard import (
    M20DestinationGuardViolation,
    WindowsNativeOps,
)


class WindowsNativeExecutionControlAdmissionTests(unittest.TestCase):
    def test_reserved_control_directory_is_the_only_native_directory_exception(self):
        backend = object.__new__(WindowsNativeOps)
        calls = []

        def open_relative(parent, name, **kwargs):
            calls.append((parent, name, kwargs))
            return 7

        backend._nt_create_relative = open_relative
        self.assertEqual(backend.open_relative_directory(3, ".m20_execution_control"), 7)
        self.assertTrue(calls[-1][2]["allow_reserved_execution_control"])

        with self.assertRaises(M20DestinationGuardViolation):
            WindowsNativeOps._name(".m20_execution_control")
        with self.assertRaises(M20DestinationGuardViolation):
            WindowsNativeOps._name(".forbidden", allow_reserved_execution_control=True)


if __name__ == "__main__":
    unittest.main()
