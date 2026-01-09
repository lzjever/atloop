Getting Started Tutorial
========================

This tutorial will guide you through your first atloop task.

Prerequisites
-------------

* Python 3.8 or higher
* atloop installed (see :doc:`../installation`)
* A sandbox backend (or use local_test mode)
* LLM API credentials configured

Step 1: Configure atloop
-------------------------

Create configuration file at ``~/.atloop/config/atloop.yaml``:

.. code-block:: yaml

   ai:
     completion:
       model: "deepseek-chat"
       api_base: "https://api.deepseek.com"
       api_key: "${DEEPSEEK_API_KEY}"
   
   sandbox:
     base_url: "http://127.0.0.1:8080"
     local_test: true  # Use local test mode for development

Step 2: Create a Simple Task
------------------------------

Create a Python script:

.. code-block:: python

   from atloop.api import TaskRunner
   from atloop.config.models import TaskSpec, Budget

   task = TaskSpec(
       task_id="my-first-task",
       goal="Add a hello_world() function to main.py",
       workspace_root="./test-project",
       task_type="feature",
       budget=Budget(max_llm_calls=10, max_tool_calls=50),
   )

   runner = TaskRunner()
   result = runner.execute(task)
   print(result)

Step 3: Review Results
-----------------------

Check the result:

.. code-block:: python

   if result["status"] == "success":
       print(f"✅ Task completed in {result['step']} steps")
       # Review the diff
       print(result.get('diff', ''))
   else:
       print(f"❌ Task failed: {result.get('reason')}")

Next Steps
----------

* :doc:`configuration` - Learn about configuration options
* :doc:`advanced_usage` - Advanced features and patterns
