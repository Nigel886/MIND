# M16 Cohort A Held-Out Task Suite

## Purpose

This document freezes the formal M16 Cohort A task suite. It reports suite
structure and reproducibility identifiers only; no benchmark was executed.

## Protocol Version

M16 protocol version: `1.1.0`.

## Suite Version

Formal suite version: `1.0.0`. Generator version:
`m16-cohort-a-generator-v1`.

## Case Distribution

| Family | Easy | Medium | Hard | Total |
| --- | ---: | ---: | ---: | ---: |
| `direct_answer` | 16 | 16 | 16 | 48 |
| `calculator` | 16 | 16 | 16 | 48 |
| Total | 32 | 32 | 32 | 96 |

## Direct-Answer Family

Public input is exactly `{"value": <public JSON-compatible value>}`. Easy
values are primitives; medium values are modest structured objects; hard values
use bounded mixed list/object nesting. There are no extra input keys.

## Calculator Family

Public input is exactly `{"operation": "add" | "multiply", "operands":
[<int>, <int>]}`. Easy uses non-negative integers 0–9; medium uses mixed-sign
integers with absolute magnitude 10–999; hard uses mixed-sign or
negative-negative integers with absolute magnitude at least 1,000. Each case
permits one deterministic calculator call only.

## Difficulty Definitions

Difficulty is assigned by deterministic construction rules before execution.
It does not depend on any observed Agent result and does not add planning,
recovery, prose extraction, multi-step arithmetic, or multiple tools.

## Agent-Visible Schema

Each Task contains only its public input, Goal, and frozen
`Task.metadata["m16_cohort_a"]` eligibility marker. It contains no expected
answer, solution, judge configuration, or private held-out administration.

## Evaluator-Private Truth

Every envelope holds immutable `M16PrivateTruth`. Direct truth is the canonical
public value; calculator truth is the deterministic integer result. Truth is
not included in Task, feedback, trace, or public outcome payload.

## Held-Out Policy

The suite is separate from M14 development fixtures and may not be used for
prompt, provider, baseline, runner, or judge debugging.

## Generation Method

Deterministic local templates and fixed indices produce ordered cases. No LLM,
provider, random seed, Agent, or benchmark runner is used.

## Duplicate Controls

Construction rejects duplicate IDs, duplicate public tasks within a family,
duplicate private envelopes, invalid schemas/eligibility, and incorrect balance.
It does not claim complete semantic-duplicate elimination.

## Canonical Serialization

The full private envelope is canonical finite JSON with sorted keys, compact
separators, UTF-8, and deterministic ordering. It includes public Task, private
truth, family/difficulty, held-out state, versions, environment, judge, and
membership; it is never supplied to an Agent.

## Suite Hash

`a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c`

## Split Hash

`a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3`

## Leakage Boundary

No public Task contains `expected_answer`; M16 does not reuse M14 public
`completion_context`. The MIND path uses only its private constant-null
compatibility sentinel, while the Direct baseline receives the original Task.

## Known Limitations

This is a frozen suite, not a result. It supports only the restricted
partial-comparability families and no claim about planning, recovery, general
agent quality, or broad reasoning superiority.
