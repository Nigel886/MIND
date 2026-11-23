"""Candidate-local scratch allocation for native-free tests only."""
from pathlib import Path
from tempfile import TemporaryDirectory as _TemporaryDirectory

SCRATCH_PARENT = Path.cwd() / ".native-free-test-scratch"
SCRATCH_PARENT.mkdir(exist_ok=True)
if not SCRATCH_PARENT.is_dir():
    raise RuntimeError("candidate-local scratch parent is unavailable")

def TemporaryDirectory(*args, **kwargs):
    if "dir" in kwargs:
        raise TypeError("native-free tests must use the verified candidate-local scratch parent")
    return _TemporaryDirectory(*args, dir=SCRATCH_PARENT, **kwargs)
