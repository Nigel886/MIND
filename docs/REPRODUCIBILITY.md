# Reproducibility and Evaluation Execution Guide

This guide reproduces the completed local MIND artifact from a clean checkout.
It covers verification, the runtime and Goal-Directed Agent demonstrations, the
M7 runtime benchmark, and the frozen M10 comparative-evaluation protocol.

## 1. Environment Requirements

- Python 3.11 or later is required. The current validation environment uses
  CPython, but no implementation-specific behavior is required.
- Run commands from the repository root so the src, evaluation, examples, and
  benchmark packages are importable.
- The repository has no third-party runtime dependency list; the completed
  commands use the Python standard library and repository code only.
- Network access, an LLM, external services, and external datasets are not
  required.

## 2. Installation

Clone the repository and enter its root directory:

    git clone https://github.com/Nigel886/MIND.git
    cd MIND

For an isolated development interpreter, create and activate a virtual
environment using your platform's normal Python command:

    python -m venv .venv

The current pyproject.toml declares the Python-version requirement but does
not define third-party dependencies or an installable build backend. Therefore,
no dependency-installation command is required for the documented artifact
commands; run them directly from the checkout. Do not treat this guide as a
claim that editable package installation is part of the current release
contract.

## 3. Verification

Run the complete regression suite:

    python -m unittest

A successful run reports all repository tests passing. At the M11 Issue #43
baseline, this is 193 tests.

## 4. Runtime Demonstration

Run the bounded runtime-foundation demonstration:

    python -m src.main

This exercises the immutable M7 runtime flow and prints a serialized
RuntimeState. Generated UUIDs and timestamps vary between executions; the
demonstrated state-transition semantics are the relevant reproducibility
property.

## 5. Goal-Directed Agent Demonstration

Run the bounded M8 Goal-Directed Agent example:

    python -m examples.goal_directed_agent_demo

The example executes the supported Calculator task 17 * 23 and prints a
serialized AgentResult with answer 391. It demonstrates controlled local tool
use and bounded task completion; it is not a general-purpose planning or
natural-language benchmark.

## 6. Benchmark Execution

Run the M7 runtime engineering benchmark:

    python -m benchmark.runtime_benchmark

The benchmark performs three bounded local repetitions and reports durations,
semantic signatures, and deterministic-consistency information. Durations and
benchmark timestamps are descriptive local measurements and are not expected to
be identical across machines or executions. The benchmark does not evaluate
Agent quality, reasoning quality, Meta-Inference quality, or intelligence.

## 7. M10 Comparative Evaluation Reproduction

M10 uses only the ordered immutable fixtures returned by
get_default_evaluation_scenarios(). The frozen protocol contains 10 local
scenarios and runs each scenario three times for two explicitly configured
baselines:

- **Baseline A:** GoalDirectedAgent(tool_registry).
- **Baseline B:** GoalDirectedAgent(tool_registry, meta_inference_engine).

The sole intended difference is explicit Meta-Inference injection. Reproduce the
full protocol from a Python session or a script run at the repository root:

    from evaluation.results.comparative_experiments import (
        execute_comparative_experiments,
    )

    results = execute_comparative_experiments()
    assert len(results) == 10
    assert sum(len(result.baseline_results) for result in results) == 60

execute_comparative_experiments() constructs the frozen baselines and invokes
the existing runner. Each result contains three repetition-indexed runs for
Baseline A and three for Baseline B, compact semantic/evidence summaries, and
metrics derived by the existing evaluation-metrics module.

The execution pipeline is:

    Frozen EvaluationScenario
            |
            v
    EvaluationRunner (Baseline A and Baseline B)
            |
            v
    Compact EvaluationRunResult values
            |
            v
    EvaluationMetrics
            |
            v
    ComparativeExperimentResult summaries
            |
            v
    M10 Comparative Evaluation Report

The published observed outcomes and metric interpretation are in
[M10 Comparative Evaluation Report](evaluation/M10-Comparative-Evaluation-Report.md).

## 8. Reproducibility Boundaries and Limitations

- The evaluation is deterministic and local. Repeated runs should preserve the
  documented decision, status, termination, compact-evidence, and semantic
  behavior for each frozen scenario/baseline group.
- UUIDs, timestamps, elapsed durations, and machine-local benchmark timings are
  intentionally not semantic equality targets.
- The protocol uses deterministic handcrafted scenarios only; it has no
  external benchmark, external dataset, network dependency, or LLM dependency.
- The results are bounded protocol observations. They do not establish
  intelligence, reasoning improvement, generalization, or superiority of either
  baseline.
- The artifact does not provide adaptive learning, online strategy adaptation,
  unrestricted tools, browser/search/API/shell/file access, or multi-agent
  execution.

## 9. Command Summary

Run these commands from the repository root:

    python -m unittest
    python -m src.main
    python -m examples.goal_directed_agent_demo
    python -m benchmark.runtime_benchmark

Use the Python snippet in Section 7 to execute the frozen M10 protocol. No
documented command requires network access.
