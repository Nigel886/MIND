# Contributing to MIND
 
 Thank you for your interest in contributing to **MIND (Meta-Inference Network Dynamics)**.
 
 We welcome contributions that improve the project, including research discussions, documentation, software implementation, testing and benchmarking.
 
 ---
 
 # Development Workflow
 
 The project follows a specification-driven development process.
 
 Every implementation should follow the documentation in the following order:
 
 1. RFC Documents
 2. Software Requirements Specification (SRS)
 3. Software Architecture Specification (SAS)
 4. Prototype Development Plan
 
 Implementation should never contradict the project specifications.
 
 ---
 
 # Getting Started
 
 1. Fork the repository.
 2. Create a feature branch.
 
 ```bash
 git checkout -b feat/your-feature
 ```
 
 3. Implement your changes.
 4. Run tests.
 5. Commit using Conventional Commits.
 6. Submit a Pull Request.
 
 ---
 
 # Commit Convention
 
 Use Conventional Commits.
 
 Examples:
 
 ```text
 feat(runtime): implement runtime lifecycle
 
 feat(belief): add belief serialization
 
 fix(policy): correct policy generation
 
 docs: update architecture specification
 
 test(runtime): add lifecycle tests
 ```
 
 ---
 
 # Coding Standards
 
 All contributions should follow:
 
 * Python 3.11+
 * PEP 8
 * Type hints
 * Google-style docstrings
 * Small, focused functions
 * High cohesion
 * Low coupling
 
 ---
 
 # Pull Request Checklist
 
 Before submitting a Pull Request, ensure that:
 
 * [ ] The implementation follows the SRS.
 * [ ] The implementation follows the SAS.
 * [ ] Unit tests pass.
 * [ ] Documentation is updated if necessary.
 * [ ] No unrelated files are modified.
 
 ---
 
 # Reporting Issues
 
 Bug reports should include:
 
 * Operating system
 * Python version
 * Steps to reproduce
 * Expected behavior
 * Actual behavior
 
 ---
 
 # Research Contributions
 
 Research discussions are welcome.
 
 Potential contribution areas include:
 
 * Active Inference
 * Belief Representation
 * World Models
 * Runtime Architecture
 * Multi-Agent Systems
 * Benchmark Design
 
 ---
 
 Thank you for helping improve the MIND project.
