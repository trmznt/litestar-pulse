Installation
============

[tbw]

Setup
=====

Initialize the database::

    uv run litestar pulsemgr db-init

Run the application::

    uv run litestar run --reload --reload-dir ../../envs/litestar-pulse/ --debug --pdb

Run tests::

    uv run python -m pytest tests

Run tests with unittest discovery::

    uv run python -m unittest discover -s tests -p "test_*.py"

Run a single test module::

    uv run python -m pytest tests/test_formbuilder_proxy_values.py


