Bugfix Task Example
===================

This example shows how to use atloop to fix bugs in code.

Example: Fix Failing Tests
--------------------------

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   task = TaskSpec(
       task_id="fix-tests",
       goal="Fix all failing tests in the test suite",
       workspace_root="./project",
       task_type="bugfix",
       constraints=[
           "All tests must pass",
           "No breaking changes",
           "Maintain backward compatibility",
       ],
       budget=Budget(
           max_llm_calls=50,
           max_tool_calls=200,
           max_wall_time_sec=600,
       ),
   )

   runner = TaskRunner()
   result = runner.execute(task)

   if result["status"] == "success":
       print("✓ All tests fixed!")
       print(f"Modified files: {result.get('modified_files', [])}")
   else:
       print(f"❌ Fix failed: {result.get('reason')}")

CLI Usage
---------

.. code-block:: bash

   atloopc execute \
     --goal "Fix all failing tests in the test suite" \
     --workspace ./project \
     --task-type bugfix \
     --constraint "All tests must pass" \
     --constraint "No breaking changes"
