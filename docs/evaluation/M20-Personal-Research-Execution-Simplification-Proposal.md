# M20 Personal Research Execution Simplification Proposal

## Recommendation

Retain **Option A**: the existing Ed25519 verifier with one owner-controlled,
encrypted signing key and one external owner trust anchor. Do not require a
separate Windows account or multi-party governance. This is the smallest safe
change because the implementation already provides canonical scope binding,
default-deny behavior, separate trust-anchor lookup, and pre-transport
verification. The remaining work is owner provisioning and explicit approval,
not an authorization redesign.

Option B—an unsigned local filesystem permit—would remove key custody and
signature complexity, but makes a process running as the owner able to create
its own execution permit. Local ACLs protect against casual access, not owner
session compromise, malware, accidental permit edits, or provenance disputes.
It would also require new permit schema, storage, integrity, and operator
confirmation code, so it is not the faster safe route.

## Security assumptions and tradeoffs

Option A assumes the owner protects an encrypted private key and passphrase,
verifies the external anchor fingerprint, and explicitly approves a bounded
run. It gives tamper-evident approval provenance and keeps the runner unable to
self-authorize. Its cost is one key provisioning/enrollment workflow.

Option B assumes the local owner account and filesystem are sufficient approval
separation. It is operationally simpler but weakens provenance and increases
the blast radius of local compromise. It is not recommended for publication-
oriented empirical evidence.

## Owner adoption

**Selected option: A — Single-Owner Ed25519 Authorization.** The owner has
approved this governance choice for future authorization. The encrypted Ed25519
private key may be held under the existing Windows user account, outside the
Git repository. A separate Windows account is not required. The owner
explicitly accepts the residual risk that same-account processes are not
strongly isolated. Option B remains an unadopted alternative.

This approval is not empirical execution approval. Owner key generation was
previously approved but has not occurred. Trust-anchor enrollment, live
authorization issuance, real feasibility execution, provider calls,
calibration, pilot, formal evaluation, and frozen-protocol changes remain
**NOT AUTHORIZED**.

## Mandatory safeguards under either future decision

Keep exact frozen manifest/membership and 24 Fixed-only originals; default deny;
explicit owner approval; provider/model identity; ceiling-v2 interaction and
replacement bounds; an owner-set maximum monetary budget; immutable canonical
evidence; safe resume/idempotence; evaluator-private H1--H4 diagnostics; and
historical-evidence immutability.

## Minimal path to the 24-work study

1. Owner explicitly authorizes key generation, then provisions one encrypted
   Ed25519 key outside the repository.
2. Owner verifies public-key fingerprint and explicitly authorizes external
   trust-anchor enrollment.
3. Owner approves exact execution budget (including maximum monetary cost),
   provider/model, and frozen 24-work scope.
4. Owner signs the exact canonical authorization envelope outside the runner.
5. A fresh independent technical audit validates the anchor, signature,
   preflight, budget, and fake transport boundary.
6. Only a separate explicit execution authorization may start the feasibility
   runner.

## If Option B is explicitly approved later

Proposed code changes would be limited to: a versioned permit schema containing
the same frozen fields plus budget; a canonical local permit reader; restrictive
path/ACL and interactive preflight checks; permit digest persistence in evidence;
and fail-closed absence/tamper tests. Required tests: scope mutation, permit
path substitution, budget exhaustion, duplicate/resume, replacement, and
provider-boundary admission. This is a future migration proposal only.

## Decisions required

The owner must separately decide whether to retain Option A (recommended) or
approve Option B’s security downgrade; authorize key generation/enrollment;
choose a budget; and authorize execution. This proposal neither changes
governance nor grants execution authority.
