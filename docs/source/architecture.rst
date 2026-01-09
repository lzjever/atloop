Architecture
============

atloop follows a clean, layered design with clear separation of concerns.

System Architecture
-------------------

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                         CLI Layer                            │
   │  (atloop/cli/) - Minimal, uses varlord for argument parsing  │
   └───────────────────────┬─────────────────────────────────────┘
                           │
   ┌───────────────────────▼─────────────────────────────────────┐
   │                        API Layer                             │
   │  (atloop/api/) - TaskRunner, single execution method        │
   └───────────────────────┬─────────────────────────────────────┘
                           │
   ┌───────────────────────▼─────────────────────────────────────┐
   │                    Core Library                              │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Orchestrator (atloop/orchestrator/)                   │  │
   │  │  - AgentLoop: Thin wrapper                            │  │
   │  │  - Workflow: DISCOVER → PLAN → ACT → VERIFY          │  │
   │  │  - Coordinator: Manages state, budget, phases        │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Runtime (atloop/runtime/)                             │  │
   │  │  - SandboxAdapter: Sandbox communication             │  │
   │  │  - ToolRuntime: Tool execution                        │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ LLM (atloop/llm/)                                    │  │
   │  │  - LLMClient: AI endpoint communication (lexilux)    │  │
   │  │  - ActionJSON: Structured action parsing              │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Retrieval (atloop/retrieval/)                        │  │
   │  │  - Indexer: Workspace indexing                        │  │
   │  │  - ProjectProfile: Project analysis                   │  │
   │  │  - ContextPack: Context building                      │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Memory (atloop/memory/)                               │  │
   │  │  - MemoryManager: State management                    │  │
   │  │  - Summarizer: History compression                     │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Tools (atloop/tools/)                                 │  │
   │  │  - Registry: Tool registration                        │  │
   │  │  - Filesystem, Interaction, Search, System tools      │  │
   │  └──────────────────────────────────────────────────────┘  │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │ Config (atloop/config/)                              │  │
   │  │  - ConfigLoader: Uses varlord for type-safe config    │  │
   │  │  - Models: AtloopConfig, TaskSpec, Budget, etc.       │  │
   │  └──────────────────────────────────────────────────────┘  │
   └─────────────────────────────────────────────────────────────┘

Design Principles
-----------------

Simple
~~~~~~

* **One function, one method**: Each class has a single, clear responsibility
* **Minimal interfaces**: APIs are as simple as possible
* **Few parameters**: Functions take only necessary parameters

Clear
~~~~~

* **One class, one responsibility**: Clear separation of concerns
* **Clear directory structure**: Logical module organization
* **Clear naming**: Self-documenting code

Explicit
~~~~~~~~

* **Predictable behavior**: No hidden side effects
* **No ambiguity**: Clear error messages and behavior
* **Type safety**: varlord ensures configuration type safety

Unique
~~~~~~

* **One thing, one way**: Single workflow implementation
* **No duplication**: DRY principle throughout
* **Consistent patterns**: Same approach across modules

Workflow Phases
---------------

DISCOVER Phase
~~~~~~~~~~~~~~

* Analyzes workspace structure
* Retrieves relevant code context
* Builds project profile
* Identifies task requirements

PLAN Phase
~~~~~~~~~~

* LLM generates execution plan
* Creates structured action list
* Validates actions against constraints
* Determines next phase transition

ACT Phase
~~~~~~~~~

* Executes tools (run commands, edit files)
* Tracks file modifications
* Records execution results
* Updates agent state

VERIFY Phase
~~~~~~~~~~~~

* Runs tests and verification commands
* Validates task completion
* Checks definition of done
* Determines success or continuation

Memory Management
------------------

Automatic Compression
~~~~~~~~~~~~~~~~~~~~~~

When memory exceeds thresholds, atloop automatically:

* Compresses old attempts and decisions
* Summarizes history using LLM
* Retains important milestones
* Removes redundant information

Smart Summarization
~~~~~~~~~~~~~~~~~~~

* LLM-powered summarization for long tasks
* Preserves key decisions and context
* Maintains task awareness across steps
* Reduces context window usage

Next Steps
----------

* :doc:`api_reference/index` - API documentation
* :doc:`examples/index` - Code examples
