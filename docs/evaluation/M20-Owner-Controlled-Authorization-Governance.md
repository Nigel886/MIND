# M20 Owner-Controlled Authorization Governance

## Model

Future real-experiment governance uses **Owner-Controlled Authorization**. The
project owner—not Codex and not ordinary production code—is the approval
authority. This replaces the prospective external-independent-issuer model
only for future governance actions; it does not alter historical audit results.

## Owner responsibilities

The owner must explicitly approve or reject each real execution, maintain
private signing-key custody outside the repository and runtime, authenticate
public-key enrollment, define provider and resource budgets, rotate/revoke
keys, and make emergency stop decisions. Ed25519 verification remains
default-deny and signatures must bind exact protocol, membership, runtime,
provider, ceiling, diagnostic, and replacement scope.

## Separation and remaining gates

Codex and production application code are not approval authorities. Before any
real execution, separately approved owner key provisioning, authenticated
trust-anchor enrollment, owner budget/execution approval, owner-signed exact
authority, and independent technical readiness verification are required.
