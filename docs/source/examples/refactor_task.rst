Refactor Task Example
=====================

This example shows how to use atloop to refactor code.

Example: Refactor Legacy Code
-----------------------------

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   task = TaskSpec(
       task_id="refactor-legacy",
       goal="Refactor the legacy payment module to use dependency injection",
       workspace_root="./payment-service",
       task_type="refactor",
       constraints=[
           "All existing tests must still pass",
           "No changes to public API",
           "Improve code readability",
           "Maintain backward compatibility",
       ],
       budget=Budget(
           max_llm_calls=60,
           max_tool_calls=250,
           max_wall_time_sec=1200,
       ),
   )

   runner = TaskRunner()
   result = runner.execute(task)

   if result["status"] == "success":
       print("✓ Refactoring complete!")
       print(f"Refactored files: {result.get('modified_files', [])}")
   else:
       print(f"❌ Refactoring failed: {result.get('reason')}")

CLI Usage
---------

.. code-block:: bash

   atloopc execute \
     --goal "Refactor the legacy payment module to use dependency injection" \
     --workspace ./payment-service \
     --task-type refactor \
     --constraint "All existing tests must still pass" \
     --constraint "No changes to public API"
