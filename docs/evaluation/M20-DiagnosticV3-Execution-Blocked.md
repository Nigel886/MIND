# M20 Diagnostic v3 Execution Blocked

The two authorized v3 work items executed once each and were persisted, but
canonical evidence reload rejects both with `retry/resource accounting mismatch`.
The execution stopped after those two work items; no retry, replay, mutation,
or third provider request is authorized.

This is an evidence-integrity blocker, not a calibration or performance result.
A separate remediation issue must diagnose and correct the persisted
retry/resource accounting contract before any new diagnostic authorization.
