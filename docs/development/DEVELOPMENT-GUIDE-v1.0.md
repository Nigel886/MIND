# DEVELOPMENT-GUIDE-v1.0

Version: v1.0

Status: Official Development Guide

---

# 1. Purpose

This document defines the official development workflow for the MIND-Lite project.

It establishes a standardized process for implementing, reviewing and maintaining the MIND-Lite reference implementation.

The guide is intended for all contributors, including both human developers and AI coding assistants.

This document complements, but does not replace, the project specifications defined by the SRS, SAS and ADRs.

---

# 2. Development Principles

The MIND project follows a Specification-Driven Development (SDD) workflow.

Software specifications are considered the single source of truth throughout the development lifecycle.

Implementation must always follow the approved specifications.

Implementation must never redefine or reinterpret the architecture.

Whenever inconsistencies or ambiguities are discovered, implementation shall stop until the specifications have been clarified.

The development process follows the principle:

Research → Specification → Architecture → Implementation → Review

Every implementation task must therefore begin with understanding the specifications rather than writing code.

---

## Core Principles

### Principle 1 — Specification First

Implementation begins only after the relevant specifications have been reviewed.

No implementation should rely on assumptions.

---

### Principle 2 — Architecture Before Code

Architectural decisions must be finalized before implementation.

Implementation exists to realize the architecture, not to redesign it.

---

### Principle 3 — Incremental Development

Development proceeds milestone by milestone.

Each milestone must be independently reviewable.

Future milestones must never be implemented in advance.

---

### Principle 4 — Explicit Review

Every implementation must pass an architecture review and a code review before it is accepted.

Implementation is not considered complete until the review process has been successfully finished.

---

### Principle 5 — Reproducibility

Every implementation step should be reproducible.

Development history, specifications and implementation decisions should remain traceable through version control.

---

# 3. Project Roles

The MIND project separates architectural decision-making from implementation.

Each participant has clearly defined responsibilities.

---

## Project Lead

Responsibilities:

- define the project vision;
- approve specifications;
- prioritize development milestones;
- make final project decisions.

The Project Lead owns the project direction.

---

## Software Architect

Responsibilities:

- review software architecture;
- define and maintain ADRs;
- review implementation plans;
- review code quality;
- ensure consistency with the SRS and SAS.

The Software Architect owns the software architecture.

---

## Implementation Engineer

Responsibilities:

- implement approved specifications;
- follow development prompts;
- report specification ambiguities;
- produce development reports;
- never redesign the architecture.

The Implementation Engineer owns implementation quality but does not make architectural decisions.

Implementation Engineers may be human developers or AI coding assistants.

---

## Responsibility Matrix

| Activity | Project Lead | Software Architect | Implementation Engineer |
|----------|:------------:|:------------------:|:-----------------------:|
| Research Direction | ✓ | | |
| SRS Approval | ✓ | ✓ | |
| SAS Approval | ✓ | ✓ | |
| ADR Approval | ✓ | ✓ | |
| Architecture Design | | ✓ | |
| Implementation | | | ✓ |
| Architecture Review | | ✓ | |
| Code Review | | ✓ | |
| Final Acceptance | ✓ | ✓ | |

---

# 4. Specification Hierarchy

The MIND project adopts a hierarchical specification system.

Higher-level specifications always take precedence over lower-level specifications.

When conflicts occur, implementation shall follow the highest applicable specification.

The specification hierarchy is defined as follows:

```
Research Vision
        │
        ▼
RFC
        │
        ▼
Software Requirements Specification (SRS)
        │
        ▼
Software Architecture Specification (SAS)
        │
        ▼
Architecture Decision Records (ADR)
        │
        ▼
Development Prompt
        │
        ▼
Implementation
```

---

## Responsibilities of Each Specification

### RFC

Defines research motivation, long-term vision and theoretical foundations.

RFCs explain **why** the project exists.

---

### SRS

Defines the functional and non-functional requirements.

The SRS explains **what** the software should accomplish.

---

### SAS

Defines the software architecture.

The SAS explains **how** the software is organized.

---

### ADR

Defines accepted architectural decisions.

ADRs resolve architectural questions that are not fully determined by the SAS.

Accepted ADRs are considered mandatory project specifications.

---

### Development Prompt

Defines the implementation task for a specific issue.

Prompts translate project specifications into executable development tasks.

Prompts must never contradict higher-level specifications.

---

## Handling Specification Conflicts

When inconsistencies are discovered:

1. Stop implementation immediately.
2. Identify the conflicting specifications.
3. Report the inconsistency.
4. Wait for clarification.
5. Resume implementation only after the specifications have been updated or confirmed.

Implementation Engineers must never resolve specification conflicts by making assumptions.

---

# 5. Standard Development Workflow

Every implementation task follows the same development workflow.

```
GitHub Issue
        │
        ▼
Read Specifications
        │
        ▼
Specification Validation
        │
        ▼
Implementation Plan
        │
        ▼
Architecture Review
        │
        ▼
Implementation
        │
        ▼
Unit Testing
        │
        ▼
Development Report
        │
        ▼
Code Review
        │
        ▼
Commit
        │
        ▼
Merge
```

No stage may be skipped.

Each stage must be successfully completed before the next stage begins.

---

## Stage Descriptions

### Stage 1 — Read Specifications

Review all documents required for the current implementation task.

Understand the relevant SRS, SAS, ADRs and Development Prompt before beginning any work.

---

### Stage 2 — Specification Validation

Verify that the specifications provide sufficient information for implementation.

If ambiguities or inconsistencies are discovered, report them immediately.

Do not make assumptions.

---

### Stage 3 — Implementation Plan

Produce a concise implementation plan describing:

- implementation strategy;
- Python language features;
- files to modify;
- testing strategy.

No code shall be written during this stage.

Implementation begins only after approval.

---

### Stage 4 — Architecture Review

The implementation plan shall be reviewed before coding begins.

Only approved plans may proceed to implementation.

---

### Stage 5 — Implementation

Implement only the functionality defined by the current issue.

Do not implement future milestones.

Do not redesign the architecture.

---

### Stage 6 — Unit Testing

Implement and execute unit tests.

Every public API introduced during implementation must be validated.

---

### Stage 7 — Development Report

Produce a Development Report summarizing:

- completed work;
- modified files;
- public APIs;
- validation results;
- deviations.

If no deviations exist, explicitly state:

"No deviations."

---

### Stage 8 — Code Review

All implementation shall undergo code review.

Review includes:

- architecture compliance;
- API consistency;
- implementation quality;
- testing completeness;
- coding standards.

Only approved implementations may be merged.

---

# 6. Architecture Decision Workflow

Not every implementation task requires an Architecture Decision Record (ADR).

ADRs are created only when a development task introduces an architectural decision that affects the long-term design of the MIND project.

Typical examples include:

- runtime architecture;
- core data models;
- interface abstractions;
- lifecycle management;
- extensibility mechanisms.

Implementation details and coding style do not require ADRs.

---

## ADR Lifecycle

Every Architecture Decision Record follows the lifecycle below.

```
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

Only accepted ADRs are considered part of the official project specification.

Implementation Engineers must follow accepted ADRs.

They must not redesign or reinterpret accepted architectural decisions.

---

## Creating New ADRs

A new ADR should be created only if:

- multiple architectural solutions are possible;
- the decision affects future milestones;
- the decision changes software architecture;
- the decision changes public interfaces;
- the decision changes component responsibilities.

Otherwise, implementation should proceed without creating a new ADR.

---

# 7. Review and Merge Workflow

Every implementation must successfully complete the review process before being merged.

The review process consists of two independent stages.

---

## Architecture Review

Architecture Review verifies that the implementation conforms to:

- the SRS;
- the SAS;
- accepted ADRs;
- the current Development Prompt.

Architecture Review is performed before implementation begins by reviewing the Implementation Plan.

---

## Code Review

Code Review verifies:

- implementation correctness;
- API consistency;
- code quality;
- testing completeness;
- compliance with project coding standards.

Only implementations that successfully pass both reviews may be merged into the main branch.

---

## Merge Criteria

An implementation may be merged only if all of the following conditions are satisfied:

- Specification Validation completed.
- Implementation Plan approved.
- Architecture Review passed.
- Implementation completed.
- Unit tests passed.
- Development Report submitted.
- Code Review passed.
- No unresolved specification ambiguities remain.

---

# 8. Completion Criteria

A development task is considered complete only when:

- all implementation objectives have been achieved;
- all required tests pass;
- documentation remains consistent with the implementation;
- the implementation conforms to the SRS, SAS and accepted ADRs;
- all required reviews have been successfully completed.

Completion of implementation alone does not indicate task completion.

Successful review and acceptance are mandatory.

---

# 9. Continuous Development

Development of the MIND project is incremental.

Each milestone builds upon previously accepted implementations.

Future milestones must not modify the responsibilities of completed milestones unless a new ADR explicitly revises the architecture.

Architectural stability is considered a primary project objective.

---

# End of Document

**Document:** DEVELOPMENT-GUIDE-v1.0

**Version:** v1.0

**Status:** Official Development Guide

This document defines the official development workflow for the MIND-Lite project.

All contributors, including human developers and AI coding assistants, are expected to follow this guide throughout the software development lifecycle.