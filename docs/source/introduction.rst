Introduction
============

What is atloop?
---------------

**atloop** (Tool-Integrated Task Automation Node) is an AI-powered task automation system that autonomously executes coding tasks in isolated sandbox environments. It understands task requirements, analyzes code, generates solutions, executes changes, and verifies results—all while maintaining complete auditability through structured logging and reporting.

Key Features
------------

* **Autonomous Execution**: atloop analyzes codebases, identifies issues, and fixes them automatically
* **Sandbox Isolation**: All changes execute in isolated environments—your workspace stays safe
* **Structured Workflow**: DISCOVER → PLAN → ACT → VERIFY cycle ensures reliable execution
* **Complete Observability**: Every action logged with full context for audit and debugging
* **Intelligent Memory**: Automatic compression and summarization for long-running tasks
* **Rich Tool Ecosystem**: Auto-discovered tools for filesystem, search, execution, and more
* **Budget Management**: Built-in budget management for LLM calls, tool calls, and execution time

Core Concepts
--------------

Workflow Phases
~~~~~~~~~~~~~~~

atloop uses a unified 4-phase workflow:

1. **DISCOVER**: Analyzes workspace, retrieves relevant context
2. **PLAN**: LLM generates execution plan and actions
3. **ACT**: Executes tools (run commands, edit files, etc.)
4. **VERIFY**: Runs tests, validates results

This cycle repeats until the task is complete or a budget limit is reached.

Task Types
~~~~~~~~~~

atloop supports three task types:

* **bugfix**: Fix bugs, ensure tests pass
* **feature**: Implement new features with tests
* **refactor**: Improve code structure, maintain behavior

Sandbox Execution
~~~~~~~~~~~~~~~~~

All code changes are executed in isolated sandbox environments. Your workspace is never modified until you review and approve the changes. This ensures:

* Safe experimentation
* Easy rollback
* Complete isolation from your development environment

Memory Management
~~~~~~~~~~~~~~~~~

atloop maintains intelligent memory of its execution:

* **Automatic Compression**: Compresses old history when context grows
* **Smart Summarization**: LLM-powered summarization for long tasks
* **Selective Retention**: Keeps important decisions and milestones

Use Cases
----------

* **Automated Bug Fixes**: Fix multiple test failures across the codebase
* **Feature Implementation**: Implement new features with tests and documentation
* **Code Refactoring**: Refactor legacy code while maintaining behavior
* **Test Generation**: Generate tests for existing code
* **Code Review Automation**: Automate simple fixes in PR reviews

Next Steps
----------

* :doc:`installation` - Install atloop
* :doc:`quickstart` - Get started quickly
* :doc:`architecture` - Understand the architecture
