# Contributing to MIND

Thank you for contributing to MIND (Meta-Inference Network Dynamics). The
repository is a specification-driven research artifact. Contributions must
preserve its documented scope, immutable-state boundaries, and reproducibility
claims.

## Development Workflow

Use an issue-based milestone workflow:

1. Read the relevant RFCs, SRS, SAS, ADRs, ROADMAP, and existing implementation.
2. Complete specification validation and architecture review before changing an
   architectural API or behavior.
3. Freeze the approved public API, boundaries, acceptance criteria, and test
   plan before implementation.
4. Keep each change scoped to its issue. Do not combine unrelated refactoring or
   unapproved future-milestone work.
5. Run the targeted tests, the complete unittest suite, and git diff --check.
6. Produce the required development report and code review record. Update
   documentation when behavior, public API, or project status changes.
7. Commit using Conventional Commits only after the review approves the scope.

The current repository is maintained through a solo-development workflow:
implementations are delivered on an issue branch, reviewed, fast-forward merged
to main, pushed, and then closed on GitHub. Do not create a Pull Request unless
the maintainer explicitly requests one.

## Getting Started

1. Clone the repository and create an issue-specific branch.

       git switch main
       git pull origin main
       git switch -c M<milestone>-<ShortIssueName>

2. Run the regression suite before and after changes.

       python -m unittest

3. Use the documented runtime, Agent, benchmark, and evaluation entry points in
   README.md and docs/REPRODUCIBILITY.md when relevant.

The current artifact requires Python 3.11 or later and declares no third-party
runtime dependencies.

## Documentation Requirements

Documentation is part of the deliverable.

- Keep README, ROADMAP, SRS, SAS, ADRs, and public API documentation consistent
  with the delivered scope.
- Record architecture review, development report, and code review material as
  required by the milestone workflow.
- Do not present deterministic local validation as intelligence improvement,
  reasoning superiority, generalization, or autonomous learning.
- Do not alter an accepted ADR merely to accommodate implementation; raise a
  specification or architecture issue instead.

## Testing and Scope Checklist

Before delivery, confirm:

- [ ] The change follows approved requirements and architecture decisions.
- [ ] Targeted tests and python -m unittest pass.
- [ ] git diff --check passes.
- [ ] Public API and documentation changes are consistent.
- [ ] No unrelated files, generated artifacts, or ignored .ai records are
      staged.
- [ ] Development report and code review conclude that the change is ready.

## Commit Convention

Use Conventional Commits with a concise scoped subject. Examples:

    feat(runtime): implement runtime lifecycle
    feat(belief): add belief serialization
    fix(policy): correct policy generation
    docs: update architecture specification
    test(runtime): add lifecycle tests
    chore: finalize release metadata and repository hygiene

## Reporting Issues

Bug reports should include:

- operating system;
- Python version;
- steps to reproduce;
- expected behavior;
- actual behavior; and
- the relevant command output when safe to share.

## Research Contributions

Potential research directions are welcome only through a new approved
specification and architecture review. Existing MIND artifacts do not provide
unrestricted tools, network access, LLM integration, online learning, or
multi-agent execution.
