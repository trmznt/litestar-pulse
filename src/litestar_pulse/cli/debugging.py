# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

"""Helpers for pulsemgr CLI debugging."""

from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable
from typing import Any, Optional

import anyio
import click

ENV_FLAG = "PULSE_CLI_IPDB"
META_IPDB_FLAG = "pulsemgr_use_ipdb"


class PulseManagerGroup(click.Group):
    """Group that can drop into ipdb when commands crash."""

    def invoke(self, ctx: click.Context) -> Any:  # type: ignore[override]
        try:
            result = super().invoke(ctx)
            return _resolve_result(result)
        except Exception as exc:  # noqa: BLE001
            if _should_enter_ipdb(ctx):
                _enter_ipdb(exc)
            raise


def _should_enter_ipdb(ctx: click.Context) -> bool:
    flag_from_ctx = bool(ctx.meta.get(META_IPDB_FLAG, False))
    if flag_from_ctx:
        return True

    env_value = os.getenv(ENV_FLAG, "").strip().lower()
    return env_value in {"1", "true", "yes", "on"}


def _enter_ipdb(exc: BaseException) -> None:
    debugger = _load_ipdb()
    if debugger is None:
        click.echo("ipdb is not installed; reraising exception.", err=True)
        return

    click.echo("ipdb: entering post-mortem debugging session...", err=True)
    debugger.post_mortem(exc.__traceback__)


def _load_ipdb() -> Optional[Any]:
    try:
        import ipdb  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return None
    return ipdb


def _resolve_result(value: Any) -> Any:
    if inspect.isawaitable(value):
        return _run_awaitable(value)
    return value


def _run_awaitable(awaitable: Awaitable[Any]) -> Any:
    async def _runner() -> Any:
        return await awaitable

    return anyio.run(_runner)


# EOF
