Quick Start
===========

This guide will help you get started with atloop in minutes.

Basic Usage
-----------

Using the CLI
~~~~~~~~~~~~~

The simplest way to use atloop is through the command-line interface:

.. code-block:: bash

   # Fix a failing test
   atloopc execute \
     --goal "Fix the failing test_add function" \
     --workspace /path/to/project \
     --task-type bugfix

   # Implement a new feature
   atloopc execute \
     --goal "Add user authentication with JWT tokens" \
     --workspace /path/to/project \
     --task-type feature

Using the Python API
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   # Create task specification
   task = TaskSpec(
       task_id="fix-test-failure",
       goal="Fix the failing test_add function in test_math.py",
       workspace_root="/path/to/project",
       budget=Budget(max_llm_calls=20, max_tool_calls=100, max_wall_time_sec=600),
   )

   # Execute - atloop handles everything
   runner = TaskRunner()
   result = runner.execute(task)

   # Review results
   if result["status"] == "success":
       print(f"✅ Task completed in {result['step']} steps")
       print(f"📝 Diff:\n{result['diff']}")
       print(f"📊 Budget used: {result['budget_used']}")
   else:
       print(f"❌ Task failed: {result['reason']}")

Task Types
----------

Bugfix Tasks
~~~~~~~~~~~~

Fix bugs in code:

.. code-block:: python

   task = TaskSpec(
       task_id="fix-bug",
       goal="Fix the bug in calculate_total() function",
       workspace_root="./project",
       task_type="bugfix",
       constraints=["All tests must pass", "No breaking changes"],
   )

Feature Tasks
~~~~~~~~~~~~~

Implement new features:

.. code-block:: python

   task = TaskSpec(
       task_id="add-feature",
       goal="Implement user authentication with JWT tokens",
       workspace_root="./api-server",
       task_type="feature",
       definition_of_done=[
           "All unit tests pass",
           "Integration tests added",
           "API documentation updated",
       ],
   )

Refactor Tasks
~~~~~~~~~~~~~~

Refactor code while maintaining behavior:

.. code-block:: python

   task = TaskSpec(
       task_id="refactor",
       goal="Refactor the legacy payment module to use dependency injection",
       workspace_root="./payment-service",
       task_type="refactor",
       constraints=[
           "All existing tests must still pass",
           "No changes to public API",
       ],
   )

Budget Management
-----------------

Control execution costs:

.. code-block:: python

   from atloop.config.models import Budget

   # Small fixes
   budget = Budget(
       max_llm_calls=10,
       max_tool_calls=50,
       max_wall_time_sec=300,
   )

   # Medium tasks
   budget = Budget(
       max_llm_calls=30,
       max_tool_calls=150,
       max_wall_time_sec=900,
   )

   # Large features
   budget = Budget(
       max_llm_calls=80,
       max_tool_calls=300,
       max_wall_time_sec=1800,
   )

Configuration
-------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

You can override configuration using environment variables:

.. code-block:: bash

   export ATLOOP__AI__COMPLETION__MODEL="gpt-4-turbo"
   export ATLOOP__AI__COMPLETION__API_BASE="https://api.openai.com/v1"
   export ATLOOP__DEFAULT_BUDGET__MAX_LLM_CALLS=100

Configuration Files
~~~~~~~~~~~~~~~~~~~

Create ``~/.atloop/config/atloop.yaml`` or ``./.atloop/config/atloop.yaml``:

.. code-block:: yaml

   ai:
     completion:
       model: "deepseek-chat"
       api_base: "https://api.deepseek.com"
       api_key: "${DEEPSEEK_API_KEY}"
   
   sandbox:
     base_url: "http://127.0.0.1:8080"
     local_test: false
   
   default_budget:
     max_llm_calls: 50
     max_tool_calls: 200
     max_wall_time_sec: 600

Next Steps
----------

* :doc:`api_reference/index` - Complete API reference
* :doc:`examples/index` - More examples
* :doc:`architecture` - Understand the architecture
