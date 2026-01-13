Feature Task Example
====================

This example shows how to use atloop to implement new features.

Example: Add Authentication
---------------------------

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   task = TaskSpec(
       task_id="add-auth",
       goal="Implement user authentication with JWT tokens, including tests and API docs",
       workspace_root="./api-server",
       task_type="feature",
       definition_of_done=[
           "All unit tests pass",
           "Integration tests added",
           "API documentation updated",
           "Security best practices followed",
       ],
       budget=Budget(
           max_llm_calls=80,
           max_tool_calls=300,
           max_wall_time_sec=1800,
       ),
   )

   runner = TaskRunner()
   result = runner.execute(task)

   if result["status"] == "success":
       print("✓ Feature implemented!")
       print(f"Files created: {result.get('created_files', [])}")
       print(f"Files modified: {result.get('modified_files', [])}")
   else:
       print(f"❌ Implementation failed: {result.get('reason')}")

CLI Usage
---------

.. code-block:: bash

   atloopc execute \
     --goal "Implement user authentication with JWT tokens" \
     --workspace ./api-server \
     --task-type feature \
     --definition-of-done "All unit tests pass" \
     --definition-of-done "Integration tests added"
