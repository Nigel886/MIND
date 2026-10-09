# M20 Owner Feasibility Execution Remediation

Issue #330 changes no frozen scientific manifest, case membership, evaluator,
diagnostic, historical evidence, or replacement eligibility.

## Owner authorization semantics

The exact future live authorization payload now names
`owner_controlled_authorization` and uses
`m20_feasibility_owner_live_authorization_v1`. It still requires an external
Ed25519 trust anchor, a trusted issuer mapping, a valid signature, and exact
binding to the frozen Fixed-only feasibility scope before any transport.

## Restrictive execution controls

The signed payload binds deterministic aggregate logical-provider limits derived
from the frozen universe: 192 for 24 originals, 192 for at most one eligible
first replacement per original, and 384 total. A durable, authorization-bound
ledger is charged before each logical provider operation; retries remain within
the same logical operation. A caller must supply an operator-stop path. Its
presence blocks the next logical operation before request construction or
transport.

These controls are not a monetary hard cap. The repository has no verified
current pricing feed or provider-side account spending control. A future owner
approval must establish an enforceable monetary ceiling and stop procedure
before real execution can be authorized.

## Full-regression root-cause triage

The failed full suites were run with `D:\Conda\python.exe` (Python 3.13.9).
In that runtime, from the repository root,
`os.getcwd()` and `Path.cwd()` returned
`C:\Users\Nigel Yan\Desktop\Personal\MIND`, but `os.path.realpath(".")`
and `Path(".").resolve()` incorrectly returned
`C:\Users\Nigel Yan\Desktop\Personal\MIND\MIND`. The M18 v2/v3 runners use
`Path.resolve()` before resolving `evaluation/m18/suites_v2` or
`evaluation/m18/suites_v3`, producing a nonexistent nested path. This is an
environmental path-resolution defect, not frozen-artifact drift.

| Test cluster | Failure signature | Baseline at `343ca0875f2aee03778b4c72c872b7806f6102d9` | Current outcome | Root cause | Attribution | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| `test_m18_v2_pilot_runner` and v2-dependent diagnostic/suite tests | `M18V2PilotIntegrityError`; missing `...\\MIND\\MIND\\evaluation\\m18\\suites_v2\\manifests\\m18_suite_v2_manifest.json` | Same failure under Python 3.13.9; six-test module passes under Python 3.12.4 | Same 3.13.9 failure; six-test module passes under Python 3.12.4 in 48.918s | Broken Python 3.13.9 `realpath` / `Path.resolve()` | Environment | Use the explicit Python 3.12.4 invocation below. |
| `test_m18_v3_pilot_runner` and corrected-pilot tests | `ValueError: frozen v3 artifact drift` after resolution into the nonexistent nested root | Same setup errors under Python 3.13.9; 27 representative v2/v3/corrected tests pass under Python 3.12.4 | Not changed by #330; #330 diff does not touch M18 source/tests/artifacts | Same path-resolution defect | Environment | Use Python 3.12.4; do not regenerate frozen artifacts. |
| #330 feasibility tests | N/A in the M18 clusters | Not applicable | 9 passed in 0.838s under the prior focused run | Offline owner/budget changes behave as covered | #330 | Retain focused coverage; rerun full regression only under the corrected interpreter. |

The baseline clean worktree was created at the exact pre-#330 commit and run
without the uncommitted implementation. Its representative command used
Python 3.12.4 and passed all 27 selected M18 v2/v3/corrected/suite tests in
103.110 seconds. Thus the observed 3.13.9 failures predate #330 and are
environment-dependent.

### Minimum trustworthy regression invocation

From the repository root, use the local Python 3.12.4 installation rather than
the Conda Python 3.13.9 path-resolution environment. Set `TEMP` and `TMP` to a
workspace-local disposable directory for sandbox-compatible temporary files and
set `M20_PRIVACY_AUDIT_MATRIX_PATH` to a disposable file before executing:

```powershell
$env:TEMP = "$PWD\.issue330-temp"
$env:TMP = "$PWD\.issue330-temp"
$env:M20_PRIVACY_AUDIT_MATRIX_PATH = "$PWD\.issue330-temp\privacy-audit.json"
& 'C:\Users\Nigel Yan\AppData\Local\Programs\Python\Python312\python.exe' -m unittest
& 'C:\Users\Nigel Yan\AppData\Local\Programs\Python\Python312\python.exe' -m pytest
```

The disposable directory and audit file must be removed after validation and
must never be staged. No M18 source or frozen artifact change is indicated.

## Final offline validation

The final regression was run from the repository root with
`C:\\Users\\Nigel Yan\\AppData\\Local\\Programs\\Python\\Python312\\python.exe`
(Python 3.12.4). Before execution, `os.getcwd()` and `Path(".").resolve()`
both resolved to the repository root; the required M18 frozen paths existed;
and the workspace-local `.issue330-temp` directory was writable. `TEMP`,
`TMP`, and `M20_PRIVACY_AUDIT_MATRIX_PATH` were directed exclusively to that
disposable directory.

| Command | Result | Exit code |
| --- | --- | --- |
| `python -m unittest` | 849 tests passed in 165.363s | 0 |
| `python -m pytest` | 849 passed in 167.15s (one `PytestCacheWarning`) | 0 |
| `git diff --check` | PASS | 0 |

The pytest warning is a non-fatal inability to create `.pytest_cache` beneath
the workspace (`WinError 5`); it did not affect collection or test results.
This successful Python 3.12.4 result contrasts with the previously reproduced
Python 3.13.9 `Path.resolve()` defect described above.

## Remaining real-execution limitation

This is successful offline implementation validation only. The persisted
logical-operation ledger and operator-stop mechanism bound logical work; they
do **not** guarantee a monetary provider spending cap. Current authoritative
pricing and a provider-side account spending control have not been verified or
enforced. Real execution therefore still requires a separate owner decision
and a verified enforceable financial-cap procedure; none was issued here.

## Boundary

No private key was accessed. No authorization was issued or signed. Provider
calls, feasibility work, calibration, pilot, formal execution, and historical
evidence changes remain zero.
