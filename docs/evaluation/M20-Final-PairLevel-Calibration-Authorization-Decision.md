# M20 Final Pair-Level Calibration Authorization Decision

## Decision

**ANSWER-TERMINATION CALIBRATION EXECUTION BLOCKED.**

The v5 pair-level projection boundary rejects raw v5 records and correctly
selects ordinary, unavailable, and linked-replacement lifecycles.  However,
it does not yet bind every selected record's provider identity to the frozen
manifest-v5 identity.  A forged pair with a different, non-empty provider hash
was admitted into the statistical projection path.

Calibration execution is therefore not authorized.  A targeted remediation
must make pair-level statistical admission require exact frozen v5 identities
before a fresh independent audit can issue a live authorization artifact.

This decision does not authorize pilot or formal evaluation and does not alter
the frozen scientific contract.
