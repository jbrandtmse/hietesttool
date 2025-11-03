# Introduction

This document outlines the overall project architecture for **Python Utility for IHE Test Patient Creation and CCD Submission**, including backend systems, CLI interface, mock endpoints, and IHE transaction processing. Its primary goal is to serve as the guiding architectural blueprint for AI-driven development, ensuring consistency and adherence to chosen patterns and technologies.

**Note on Scope:** This is a command-line utility with no user interface. All user interaction occurs through terminal commands. The architecture focuses on backend processing, SOAP transaction handling, security (SAML/XML signing), and mock endpoint infrastructure.

### Starter Template or Existing Project

**Decision:** N/A - Greenfield project. Manual setup required for project structure, dependencies, and tooling.

Based on review of the PRD and Brief, this is a **greenfield project** with no starter template mentioned. The project structure will be created from scratch following Python best practices for CLI utilities.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-11-02 | 0.1 | Initial architecture document | Architect |
