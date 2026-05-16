
Litestar-Pulse
==============

Litestar-Pulse is an add-on library for Litestar to manage users, groups, and permissions with a web interface.

Installation
------------

To install Litestar-Pulse, enter to the parent directory of the intended installation
directory and execute the following command::

	"${SHELL}" <(curl -L https://raw.githubusercontent.com/trmznt/litestar-pulse/main/install.sh)

Setting up and running the server
---------------------------------

To set up the server, execute the follofing command (assuming the installation directory
is INST_DIR)::

.. code-block:: bash

	INST_DIR/bin/activate
	cd $VVG_BASEDIR/instances
	mkdir -p litestar-pulse.localhost/db
	cd litestar-pulse.localhost
	pulsemgr db-init
	pulsemgr user-passwd --username sysadm --password NEW_PASSWORD

Once the server is set up, you can run it with the following command::

.. code-block:: bash

	litestar --app litestar_pulse.lib.app:init_app run --port 7979

To run the server in development mode with auto-reload, use the following command::

.. code-block:: bash

	litestar --app litestar_pulse.lib.app:init_app run --port 7979 --reload --debug --pdb --reload-dir ${VVG_BASEDIR}/envs/tagato

Tests
-----

Run all tests (recommended)::

	uv run python -m pytest tests

Run all tests with unittest discovery (fallback)::

	uv run python -m unittest discover -s tests -p "test_*.py"

Run a single test module::

	uv run python -m pytest tests/test_formbuilder_proxy_values.py
