# Architecture Decision Records (ADR)

## Overview

Architecture Decision Records (ADRs) document significant architectural decisions made during the development of the MIND-Lite project.

Each ADR captures:

* the architectural problem;
* the decision that was made;
* the rationale behind the decision;
* the consequences of adopting the decision.

Accepted ADRs are considered part of the official project specification.

According to the project specification hierarchy:

```text
RFC
    ↓
SRS
    ↓
SAS
    ↓
Accepted ADR
    ↓
Development Prompt
    ↓
Implementation
```

All implementations shall comply with accepted ADRs.

---

# ADR Index

| ADR     | Title                   |  Status  | Milestone |
| ------- | ----------------------- | :------: | :-------: |
| ADR-001 | Immutable Belief        | Accepted |     M2    |
| ADR-002 | Immutable Runtime State | Accepted |     M3    |

---

# When to Create an ADR

A new ADR should be created when an implementation introduces a long-term architectural decision.

Typical examples include:

* introducing a new core component;
* changing component responsibilities;
* defining ownership of system behavior;
* introducing a new abstraction;
* changing public interfaces;
* defining lifecycle management;
* changing serialization strategy;
* introducing extensibility mechanisms.

Implementation details and coding style decisions do not require ADRs.

---

# ADR Lifecycle

Every ADR follows the same lifecycle.

```text
Architecture Question
        │
        ▼
Architecture Discussion
        │
        ▼
ADR Draft
        │
        ▼
Architecture Review
        │
        ▼
Accepted
        │
        ▼
Implementation
```

Only accepted ADRs are considered official project specifications.

---

# Naming Convention

ADR files follow the naming convention:

```text
ADR-XXX-Short-Title.md
```

Examples:

```text
ADR-001-Immutable-Belief.md

ADR-002-Immutable-Runtime.md

ADR-003-Inference-Ownership.md
```

ADR numbers are assigned sequentially.

Numbers are never reused.

---

# Relationship with Other Specifications

RFCs describe research concepts.

The SRS defines software requirements.

The SAS defines software architecture.

ADRs refine and clarify architectural decisions that are not fully specified by the SAS.

Development Prompts translate these specifications into implementation tasks.

ADRs therefore bridge architecture and implementation.

---

# Maintenance

An accepted ADR should remain stable.

If an architectural decision changes in the future, a new ADR should be created instead of rewriting the historical decision.

Historical ADRs provide traceability for the evolution of the MIND architecture.
