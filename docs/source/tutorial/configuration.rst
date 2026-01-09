Configuration Tutorial
======================

Learn how to configure atloop for your needs.

Configuration Sources
---------------------

atloop uses varlord for configuration management. Configuration is loaded from multiple sources in priority order:

1. Environment variables (``ATLOOP__*``) - Highest priority
2. ``.env`` file in current directory
3. Project config (``./.atloop/config/atloop.yaml``)
4. User config (``~/.atloop/config/atloop.yaml``)
5. Defaults - Lowest priority

Environment Variables
---------------------

Set configuration using environment variables:

.. code-block:: bash

   export ATLOOP__AI__COMPLETION__MODEL="gpt-4-turbo"
   export ATLOOP__AI__COMPLETION__API_BASE="https://api.openai.com/v1"
   export ATLOOP__DEFAULT_BUDGET__MAX_LLM_CALLS=100

Configuration File
------------------

Create ``~/.atloop/config/atloop.yaml``:

.. code-block:: yaml

   ai:
     completion:
       model: "deepseek-chat"
       api_base: "https://api.deepseek.com"
       api_key: "${DEEPSEEK_API_KEY}"
     embedding:
       model: "text-embedding-ada-002"
       api_base: "https://api.openai.com/v1"
       api_key: "${OPENAI_API_KEY}"
   
   sandbox:
     base_url: "http://127.0.0.1:8080"
     local_test: false
   
   default_budget:
     max_llm_calls: 50
     max_tool_calls: 200
     max_wall_time_sec: 600
   
   memory:
     summary_max_length: 64000
     llm_compression_enabled: true

Next Steps
----------

* :doc:`advanced_usage` - Learn advanced features
* :doc:`../api_reference/config` - Complete configuration reference
