Advanced Usage Tutorial
========================

Learn advanced features and patterns.

Custom Budgets
--------------

Set different budgets for different task types:

.. code-block:: python

   from atloop.config.models import Budget

   # Quick fixes
   quick_budget = Budget(
       max_llm_calls=5,
       max_tool_calls=20,
       max_wall_time_sec=120,
   )

   # Complex features
   complex_budget = Budget(
       max_llm_calls=100,
       max_tool_calls=500,
       max_wall_time_sec=3600,
   )

Custom Configuration Directory
------------------------------

Use a custom configuration directory:

.. code-block:: python

   from atloop.api import TaskRunner

   # Use custom config directory
   runner = TaskRunner(atloop_dir="/path/to/custom/config")

Task Constraints
----------------

Add constraints to guide task execution:

.. code-block:: python

   task = TaskSpec(
       goal="Refactor payment module",
       workspace_root="./project",
       task_type="refactor",
       constraints=[
           "All tests must pass",
           "No breaking changes",
           "Follow PEP 8 style guide",
           "Add type hints",
       ],
   )

Definition of Done
------------------

Specify completion criteria:

.. code-block:: python

   task = TaskSpec(
       goal="Add authentication",
       workspace_root="./api",
       task_type="feature",
       definition_of_done=[
           "All unit tests pass",
           "Integration tests added",
           "API documentation updated",
           "Security review completed",
       ],
   )

Next Steps
----------

* :doc:`../api_reference/index` - Complete API reference
* :doc:`../examples/index` - More examples
