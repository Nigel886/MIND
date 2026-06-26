# TRAE-Prototype-v1.0
 
 **AI Development Protocol**
 
 Project: **MIND-Lite**
 
 Version: **v1.0**
 
 Status: **Prototype Development**
 
 ---
 
 # 1. Mission
 
 You are the lead software engineer responsible for implementing the first executable prototype of the MIND project.
 
 Your objective is **not** to design a new agent framework.
 
 Your objective is to faithfully implement the software architecture already specified by the project documentation.
 
 This project is a research prototype.
 
 Architectural correctness is more important than feature richness.
 
 Whenever uncertainty exists, always choose the simplest implementation that satisfies the specification.
 
 ---
 
 # 2. Development Priority
 
 The implementation must strictly follow the documents below.
 
 Priority (highest → lowest):
 
 1. RFC-000 – Project Vision
 2. RFC-001 – Research Gap
 3. RFC-001A – Belief Representation
 4. RFC-001B – Concept Hierarchy
 5. RFC-002 – Research Blueprint
 6. RFC-003 – MIND Formalism
 7. SRS-MIND-Lite-v1.0
 8. Software-Architecture-Specification-v1.0
 9. README
 
 If two documents appear to conflict, follow the document with the higher priority.
 
 Do not invent new architectural decisions unless the existing documents leave the implementation unspecified.
 
 ---
 
 # 3. Development Objective
 
 The objective of Version 1.0 is to implement a **minimal but complete inference runtime**.
 
 The prototype must demonstrate the following runtime loop:
 
 ```text
 Observation
       │
       ▼
 Inference
       │
       ▼
 Belief Update
       │
       ▼
 Policy Generation
       │
       ▼
 Action Execution
       │
       ▼
 New Observation
 ```
 
 This execution loop is the core deliverable of MIND-Lite.
 
 ---
 
 # 4. Scope
 
 Only the following runtime components are included.
 
 * Observation
 * Belief
 * Inference Engine
 * Policy Engine
 * Action Executor
 * Runtime Controller
 
 Everything else is outside the scope of Version 1.0.
 
 ---
 
 # 5. Architecture Constraints
 
 The following rules are mandatory.
 
 * Do not redesign the architecture.
 * Do not rename directories.
 * Do not rename modules.
 * Do not introduce additional runtime layers.
 * Do not introduce unnecessary abstractions.
 * Do not violate module responsibilities defined in the SAS.
 * Keep every module focused on a single responsibility.
 * Prefer composition over inheritance unless inheritance is explicitly required.
 
 The architecture is considered frozen.
 
 The implementation must conform to the architecture rather than modifying it.
 
 ---
 
 # 6. Coding Standards
 
 The implementation shall follow these engineering standards.
 
 ## Language
 
 * Python 3.11+
 
 ## Style
 
 * PEP 8
 * Strong type annotations
 * Comprehensive docstrings
 * Clear naming conventions
 * Small, readable functions
 * High cohesion
 * Low coupling
 
 ## Data Structures
 
 Use:
 
 * dataclasses
 * enums
 * abstract base classes
 * typing module
 
 Avoid unnecessary complexity.
 
 ---
 
 # 7. Repository Rules
 
 Implement code only inside the existing repository structure.
 
 Do not create additional top-level directories.
 
 Do not introduce new architectural modules without explicit justification.
 
 Future extensions belong to future versions.
 
 The Version 1.0 repository should remain lightweight, readable and easy to understand.
 
 ---
