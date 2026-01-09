Installation
============

Installing atloop
-----------------

Using pip
~~~~~~~~~

.. code-block:: bash

   pip install atloop

Using uv (Recommended)
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install uv first
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install atloop
   uv pip install atloop

Development Installation
------------------------

For development, clone the repository and install in editable mode:

.. code-block:: bash

   git clone https://github.com/lzjever/atloop.git
   cd atloop

   # Using uv (recommended)
   make dev-install

   # Or using pip
   pip install -e ".[dev]"

Dependencies
------------

atloop requires:

* Python 3.8 or higher
* varlord >= 0.7.0 (Configuration management)
* lexilux >= 2.1.0 (LLM communication)
* noxrunner >= 2.0.0 (Sandbox execution)
* rich >= 13.0.0 (Console output)
* json-repair >= 0.30.0 (JSON repair)

Optional Dependencies
---------------------

* Development dependencies: ``pip install atloop[dev]``
* Documentation dependencies: ``pip install atloop[docs]``

Configuration
-------------

Create configuration file at ``~/.atloop/config/atloop.yaml``:

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

   memory:
     summary_max_length: 64000
     llm_compression_enabled: true

Verification
------------

Verify installation:

.. code-block:: bash

   python -c "import atloop; print(atloop.__version__)"

Or use the CLI:

.. code-block:: bash

   atloopc --help

Next Steps
----------

* :doc:`quickstart` - Get started with atloop
* :doc:`introduction` - Learn about atloop concepts
