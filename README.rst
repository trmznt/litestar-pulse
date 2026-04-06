
Litestar-Pulse
==============

Litestar-Pulse is an add-on library for Litestar to manage users, groups, and permissions with a web interface.

Tests
=====

Run all tests (recommended)::

	uv run python -m pytest tests

Run all tests with unittest discovery (fallback)::

	uv run python -m unittest discover -s tests -p "test_*.py"

Run a single test module::

	uv run python -m pytest tests/test_formbuilder_proxy_values.py
