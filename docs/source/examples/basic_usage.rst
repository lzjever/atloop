Basic Usage Example
===================

This example shows how to use atloop to execute a simple task.

Using the API
-------------

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   # Create task
   task = TaskSpec(
       task_id="simple-task",
       goal="Fix the syntax error in main.py",
       workspace_root="./my-project",
       budget=Budget(max_llm_calls=10, max_tool_calls=50),
   )

   # Execute
   runner = TaskRunner()
   result = runner.execute(task)

   # Check results
   if result["status"] == "success":
       print(f"Task completed in {result['step']} steps")
       print(f"Diff:\n{result.get('diff', '')}")
   else:
       print(f"Task failed: {result.get('reason', 'Unknown error')}")

Using the CLI
-------------

.. code-block:: bash

   atloopc execute \
     --goal "Fix the syntax error in main.py" \
     --workspace ./my-project \
     --task-type bugfix
