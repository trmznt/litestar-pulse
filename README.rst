
Litestar-Pulse
==============

Litestar-Pulse is an add-on library for Litestar to manage users, groups, and permissions with a web interface.

Installation
============

To install Litestar-Pulse, enter to the parent directory of the intended installation
directory and execute the following command::

	"${SHELL}" <(curl -L https://raw.githubusercontent.com/trmznt/litestar-pulse/main/install.sh)

Tests
=====

Run all tests (recommended)::

	uv run python -m pytest tests

Run all tests with unittest discovery (fallback)::

	uv run python -m unittest discover -s tests -p "test_*.py"

Run a single test module::

	uv run python -m pytest tests/test_formbuilder_proxy_values.py
