# DR-M18 Power Calibration Runner

## Scope

Issue #195 implements provider-free preparation only. No provider was called, no calibration was formally executed, and no canonical calibration evidence was created.

## Frozen design recovered

- Condition/suite: `m18_power_calibration_v1`
- Design: 48 case clusters, two families × three strata × eight cases
- Universe: 48 × five paired repetitions × MIND/Direct = 480 logical runs
- Comparator contract: corrected `m18_v3_comparator_contract_v2`; only `mind_lite_v11` and `direct_tool_calling`
- IDs/schema: `m18pcv1-` / `m18_power_calibration_v1_logical_run_id_v1`
- Namespace: `evaluation/m18/results/m18_power_calibration_v1/pilot`
- Mapping boundary: calibration evidence only; the frozen nuisance-to-power procedure remains outside the runner.

## Controls

The implementation provides canonical manifest hashing, provenance closure, atomic create plus admission reread, no-overwrite/duplicate rejection, tamper rejection during record load, missing-only resume, and restart-persistent structural provider stop. Provider diagnostic text is not serialized into calibration records or stop artifacts; only finite typed stop fields persist. HTTP 5xx and timeout categories do not satisfy the structural-stop criterion.

## Validation

`tests/test_m18_power_calibration_runner.py` passes (4 tests): exact universe, unique ID domain, counts, 240 pairing cells, MIND/Direct-only dispatch contract, temporary full 480-record lifecycle, zero production-store records, missing-only behavior, duplicate rejection, tamper rejection, and CLI condition rejection. `git diff --check` passes. A full `pytest -q` run progressed beyond 40% without a failure but exceeded this environment's command window, so it is not claimed as a passing full regression.

## Authorization

Runner preparation is complete. Real calibration execution: not authorized. Formal execution: not authorized.

## Delivery state

The selective source/tests/docs/report commit is local. Push to `origin/main` was attempted but is blocked by the environment's HTTPS proxy connection to GitHub; therefore `HEAD` does not yet equal `origin/main` and Issue #195 must remain open.
