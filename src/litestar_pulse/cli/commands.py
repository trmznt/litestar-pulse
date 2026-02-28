# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from typing import NoReturn

import nest_asyncio

try:
    nest_asyncio.apply()
except Exception:
    print("nest_asyncio.apply() is not applied", file=sys.stderr)

from contextlib import asynccontextmanager
import click
from litestar import Litestar
from litestar_pulse.cli.debugging import META_IPDB_FLAG, PulseManagerGroup

from litestar_pulse.db.setup import (
    list_userdomains,
    list_users,
)


@click.group(
    name="pulsemgr",
    invoke_without_command=False,
    help="CLI manager for litestar-pulse",
    cls=PulseManagerGroup,
)
@click.option(
    "--ipdb/--no-ipdb",
    "use_ipdb",
    default=False,
    show_default=True,
    help="Drop into ipdb if a command raises an unhandled exception.",
)
def pulsemgr(use_ipdb: bool) -> None:
    """Manage litestar-pulse."""

    ctx = click.get_current_context()
    ctx.meta[META_IPDB_FLAG] = use_ipdb


@pulsemgr.command(name="db-init", help="create tables and seed demo data")
async def pulse_db_init() -> None:
    """Initialize the database and populate initial data."""

    from litestar_pulse.db.initdb import initialize_database

    click.echo("Initializing database...")
    created_enumkeys, created_groups, created_domains, created_users = (
        await initialize_database()
    )
    click.echo(
        "Ensured schema. Added "
        f"{created_enumkeys} enumkey(s), {created_groups} group(s), {created_domains} domain(s), "
        f"and {created_users} user(s)."
    )


@pulsemgr.command(name="userdomain-list", help="list user domains")
async def pulse_userdomains_list() -> None:
    """List all user domains."""
    click.echo("Listing user domains...")

    async with get_dbhandler() as dbh:
        userdomains = await dbh.repo.UserDomain.list(
            load=[dbh.func.undefer(dbh.model.UserDomain.user_count)]
        )

    if not userdomains:
        click.echo("No user domains found. Run 'pulsemgr db-init' first.")
        return

    domain_width = max(len("Domain"), *(len(ud.domain) for ud in userdomains))
    users_width = max(len("Users"), *(len(str(ud.user_count)) for ud in userdomains))

    header = f"{'Domain':<{domain_width}} {'Users':>{users_width}}  Description"
    click.echo(header)
    click.echo("-" * len(header))

    for ud in userdomains:
        click.echo(
            f"{ud.domain:<{domain_width}} {ud.user_count:>{users_width}}  {ud.desc}"
        )


@pulsemgr.command(name="user-list", help="list users")
async def pulse_user_list() -> None:
    """List all users."""
    click.echo("Listing users...")

    async with get_dbhandler() as dbh:
        users = await dbh.repo.User.list(
            #    load=[dbh.func.joinedload(dbh.model.User.domain)]
        )

    if not users:
        click.echo("No users found. Run 'pulsemgr db-init' first.")
        return

    columns = (
        ("login", "Login"),
        ("email", "Email"),
        ("name", "Name"),
        ("domain", "Domain"),
        ("institution", "Institution"),
        ("primarygroup", "Primary Group"),
    )

    widths: dict[str, int] = {}
    for key, header in columns:
        widths[key] = max(
            len(header), *(len(str(getattr(user, key))) for user in users)
        )

    header_line = "  ".join(f"{label:<{widths[key]}}" for key, label in columns)
    click.echo(header_line)
    click.echo("-" * len(header_line))

    for user in users:
        click.echo(
            "  ".join(f"{str(getattr(user, key)):<{widths[key]}}" for key, _ in columns)
        )


@pulsemgr.command(name="user-add", help="add new user")
def pulse_user_add(app: Litestar) -> None:
    """User management command group."""

    click.echo("Adding user...")
    click.echo(f"Running pulsemgr user-add app: {app.debug}")


@pulsemgr.command(name="enumkey-list", help="list enum keys")
async def pulse_enumkey_list() -> None:
    """List all enum keys."""
    click.echo("Listing enum keys...")

    async with get_dbhandler() as dbh:
        enumkeys = await dbh.repo.EnumKey.list(
            load=[dbh.func.joinedload(dbh.model.EnumKey.category)]
        )

    if not enumkeys:
        click.echo("No enum keys found.")
        return

    columns = (
        ("key", "Key"),
        ("desc", "Description"),
        ("category", "Category"),
        ("is_category", "Is Category"),
    )

    widths: dict[str, int] = {}
    for key, header in columns:
        widths[key] = max(len(header), *(len(str(getattr(ek, key))) for ek in enumkeys))

    header_line = "  ".join(f"{label:<{widths[key]}}" for key, label in columns)
    click.echo(header_line)
    click.echo("-" * len(header_line))

    for ek in enumkeys:
        click.echo(
            "  ".join(f"{str(getattr(ek, key)):<{widths[key]}}" for key, _ in columns)
        )


@pulsemgr.command(name="shell", help="run IPython shell")
def run_cli() -> NoReturn:
    """
    CLI entry point for litestar pulsemgr integrated command
    """
    import IPython

    IPython.embed(using="asyncio")


@pulsemgr.command(name="txn", help="run IPython shell within a transaction")
async def run_txn_cli() -> NoReturn:
    """
    CLI entry point for litestar pulsemgr to runn an IPython shell within
    a transaction
    """

    from litestar_pulse.config.db import DBConfig
    from litestar_pulse.db import handler_factory
    import IPython

    dbc = DBConfig()

    try:
        async with dbc.session_factory() as session:
            dbhandler = handler_factory(session)
            print(
                "Starting IPython shell with database session and handler (dbs, dbh)..."
            )
            IPython.embed(using="asyncio", user_ns={"dbs": session, "dbh": dbhandler})
    finally:
        await dbc.engine.dispose()


@asynccontextmanager
async def get_dbhandler():
    # this function can be used in a with block, and return the database handler

    from litestar_pulse.config.db import DBConfig
    from litestar_pulse.db import handler_factory
    import IPython

    dbc = DBConfig()

    try:
        async with dbc.session_factory() as session:
            dbhandler = handler_factory(session)
            yield dbhandler
    finally:
        await dbc.engine.dispose()


def main() -> NoReturn:
    """
    CLI entry point for pulsemgr standalone command
    """

    pulsemgr()


# EOF
