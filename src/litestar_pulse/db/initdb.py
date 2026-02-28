# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import logging
import secrets
from typing import Any, Dict, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from advanced_alchemy.base import orm_registry

from litestar_pulse.config.db import DBConfig
from litestar_pulse.lib.crypt import hash_password
from litestar_pulse.db.models.account import Group, User, UserDomain, UserGroup
from litestar_pulse.db.models.enumkey import EnumKey, EnumKeyRegistry

logger = logging.getLogger(__name__)

from litestar_pulse.db.fixtures import seed

SEED = seed


async def initialize_database(seed_module: Any = SEED) -> tuple[int, int, int, int]:
    """Create the database schema and seed example data."""

    config = DBConfig()
    engine = config.engine

    async with engine.begin() as conn:
        await conn.run_sync(orm_registry.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    created_enumkeys = 0
    created_groups = 0
    created_domains = 0
    created_users = 0
    enumkey_payloads, group_payloads, domain_payloads = _load_fixture_payloads(
        seed_module
    )

    try:
        async with session_factory() as session:
            created_enumkeys = await _ensure_enumkeys(session, enumkey_payloads)
            await EnumKeyRegistry.ensure_current(session)
            created_groups, group_map = await _ensure_groups(session, group_payloads)
            created_domains, domain_map, created_users = await _ensure_domains(
                session,
                domain_payloads,
                group_map,
            )
            if created_enumkeys or created_domains or created_groups or created_users:
                await session.commit()
            else:
                await session.rollback()
    finally:
        await engine.dispose()

    return created_enumkeys, created_groups, created_domains, created_users


def _load_fixture_payloads(seed_module: Any) -> tuple[
    Sequence[dict[str, Any]],
    Sequence[dict[str, Any]],
    Sequence[dict[str, Any]],
]:
    """Load fixture payloads from module file."""

    enum_specs = getattr(seed_module, "ENUMKEYS", ()) or ()
    group_specs = getattr(seed_module, "GROUPS", ()) or ()
    domain_specs = getattr(seed_module, "USERDOMAINS", ()) or ()

    enum_payloads = tuple(
        _normalize_enumkey_payload(spec, syskey=True) for spec in enum_specs
    )
    logger.info(f"Loaded {len(enum_payloads)} enumkey fixture specifications.")

    group_payloads = tuple(_normalize_group_payload(spec) for spec in group_specs)
    logger.info(f"Loaded {len(group_payloads)} group fixture specifications.")

    domain_payloads = tuple(_normalize_domain_payload(spec) for spec in domain_specs)
    logger.info(f"Loaded {len(domain_payloads)} userdomain fixture specifications.")

    return enum_payloads, group_payloads, domain_payloads


async def _ensure_enumkeys(
    session: AsyncSession,
    payloads: Sequence[dict[str, Any]],
) -> int:
    created = 0
    if not payloads:
        return created

    before = await session.scalar(select(func.count(EnumKey.id))) or 0
    for payload in payloads:
        await EnumKey.upsert_from_dict(session, payload, update=True)
    await session.flush()
    after = await session.scalar(select(func.count(EnumKey.id))) or before
    created = max(after - before, 0)
    return created


async def _ensure_groups(
    session: AsyncSession,
    payloads: Sequence[dict[str, Any]],
) -> tuple[int, Dict[str, Group]]:
    created = 0
    groups: Dict[str, Group] = {}
    if not payloads:
        return created, groups

    role_keys: set[str] = {
        role for payload in payloads for role in payload.get("roles", []) if role
    }
    enum_map: Dict[str, EnumKey] = {}
    if role_keys:
        result = await session.execute(
            select(EnumKey).where(EnumKey.key.in_(role_keys))
        )
        enum_map = {enum.key: enum for enum in result.scalars()}

    for payload in payloads:
        name = payload["name"]
        desc = payload.get("desc") or name
        group = await session.scalar(select(Group).where(Group.name == name))
        if group is None:
            group = Group(name=name, desc=desc)
            session.add(group)
            created += 1
        else:
            group.desc = desc
        groups[name] = group

        desired_roles = []
        for role_key in payload.get("roles", []):
            enum = enum_map.get(role_key)
            if enum is None:
                logger.warning("EnumKey %s not found for group %s", role_key, name)
                continue
            desired_roles.append(enum)

        if desired_roles:
            existing = {role.key for role in group.roles}
            for enum in desired_roles:
                if enum.key not in existing:
                    group.roles.append(enum)
                    existing.add(enum.key)

    return created, groups


async def _ensure_domains(
    session: AsyncSession,
    payloads: Sequence[dict[str, Any]],
    groups: Dict[str, Group],
) -> tuple[int, Dict[str, UserDomain], int]:
    created = 0
    created_users = 0
    domains: Dict[str, UserDomain] = {}

    for payload in payloads:
        name = payload["domain"]
        desc = payload.get("desc") or name
        domain_type = payload.get("domain_type") or "Internal"
        domain = await session.scalar(
            select(UserDomain).where(UserDomain.domain == name)
        )
        if domain is None:
            domain = UserDomain(domain=name, desc=desc, domain_type=domain_type)
            session.add(domain)
            created += 1
        else:
            domain.desc = desc
        domains[name] = domain

        for user_payload in payload.get("users", []):
            exists = await session.scalar(
                select(User).where(User.login == user_payload["login"])
            )
            if exists is not None:
                continue

            primary_group_name = user_payload.get("primary_group")
            primary_group = (
                groups.get(primary_group_name) if primary_group_name else None
            )
            if primary_group is None and groups:
                primary_group = next(iter(groups.values()))
            if primary_group is None:
                logger.warning(
                    "Skipping user %s because no primary group is available.",
                    user_payload["login"],
                )
                continue

            password_value, generated = _resolve_password_spec(
                user_payload.get("password")
            )
            credential = ""
            if password_value is not None:
                credential = await hash_password(password_value)
            if generated:
                logger.info(
                    "Generated password for user %s@%s: %s",
                    user_payload["login"],
                    name,
                    password_value,
                )

            user = User(
                login=user_payload["login"],
                email=user_payload.get("email")
                or f"{user_payload['login']}@{name.lower()}",
                lastname=user_payload.get("lastname") or user_payload["login"],
                firstname=user_payload.get("firstname", ""),
                institution=user_payload.get("institution", ""),
                credential=credential,
                domain=domain,
                primarygroup=primary_group,
            )
            session.add(user)
            created_users += 1

            memberships = list(user_payload.get("groups", []))
            membership_names = {m["name"] for m in memberships if m.get("name")}
            if primary_group.name not in membership_names:
                memberships.append({"name": primary_group.name, "role": "M"})

            seen_memberships: set[str] = set()
            for membership in memberships:
                group_name = membership.get("name")
                if not group_name or group_name in seen_memberships:
                    continue
                group = groups.get(group_name)
                if group is None:
                    logger.warning(
                        "Unknown group %s referenced for user %s",
                        group_name,
                        user.login,
                    )
                    continue
                role = (membership.get("role") or "M").upper()[0:1] or "M"
                user.groups.append(UserGroup(user=user, group=group, role=role))
                seen_memberships.add(group_name)

    return created, domains, created_users


def _resolve_password_spec(password: str | None) -> tuple[str | None, bool]:
    """Interpret special password markers from the fixture payload."""

    if not password:
        return None, False

    raw = password.strip()
    if raw == "{X}":
        return secrets.token_urlsafe(32), False
    if raw == "?":
        return secrets.token_urlsafe(16), True
    return raw, False


def _normalize_enumkey_payload(spec: Any, *, syskey: bool) -> dict[str, Any]:
    if isinstance(spec, dict):
        payload = dict(spec)
        key = payload.get("key")
        if not key:
            raise ValueError("EnumKey specification missing 'key'")
        payload["key"] = key
        payload["desc"] = payload.get("desc") or key
        payload["syskey"] = payload.get("syskey", syskey)
        members = payload.get("members") or payload.get("children") or []
        payload["members"] = [
            _normalize_enumkey_payload(member, syskey=False) for member in members
        ]
        return payload

    if isinstance(spec, str):
        return {"key": spec, "desc": spec, "syskey": syskey}

    if not isinstance(spec, (list, tuple)) or not spec:
        raise ValueError("Invalid EnumKey specification")

    key = spec[0]
    desc = ""
    members_spec: Any = None
    if len(spec) > 1:
        second = spec[1]
        if isinstance(second, (list, tuple)):
            members_spec = second
        else:
            desc = second or ""
    if len(spec) > 2:
        members_spec = spec[2]

    payload = {"key": key, "desc": desc or key, "syskey": syskey}
    if members_spec:
        payload["members"] = [
            _normalize_enumkey_payload(member, syskey=False) for member in members_spec
        ]
    else:
        payload["members"] = []
    return payload


def _normalize_group_payload(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        name = spec.get("name")
        if not name:
            raise ValueError("Group specification missing 'name'")
        roles = [role for role in spec.get("roles", []) if role]
        return {
            "name": name,
            "desc": spec.get("desc") or name,
            "roles": roles,
        }

    if not isinstance(spec, (list, tuple)) or not spec:
        raise ValueError("Invalid group specification")

    name = spec[0]
    roles = spec[1] if len(spec) > 1 else []
    desc = spec[2] if len(spec) > 2 else ""
    return {
        "name": name,
        "desc": desc or name,
        "roles": [role for role in (roles or []) if role],
    }


def _normalize_domain_payload(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        name = spec.get("domain")
        if not name:
            raise ValueError("Domain specification missing 'domain'")
        users = [_normalize_user_payload(user) for user in spec.get("users", [])]
        return {
            "domain": name,
            "desc": spec.get("desc") or name,
            "domain_type": spec.get("domain_type") or "Internal",
            "users": users,
        }

    if not isinstance(spec, (list, tuple)) or len(spec) < 2:
        raise ValueError("Invalid user domain specification")

    name = spec[0]
    desc = spec[1] if len(spec) > 1 else ""
    domain_type = spec[4] if len(spec) > 4 else "Internal"
    users_spec = spec[5] if len(spec) > 5 else []
    return {
        "domain": name,
        "desc": desc or name,
        "domain_type": domain_type,
        "users": [_normalize_user_payload(user) for user in users_spec or []],
    }


def _normalize_user_payload(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        groups = [_normalize_membership(entry) for entry in spec.get("groups", [])]
        payload = dict(spec)
        payload["groups"] = groups
        return payload

    if not isinstance(spec, (list, tuple)) or not spec:
        raise ValueError("Invalid user specification")

    login = spec[0]
    email = spec[1] if len(spec) > 1 else f"{login}@localhost"
    lastname = spec[2] if len(spec) > 2 else ""
    firstname = spec[3] if len(spec) > 3 else ""
    institution = spec[4] if len(spec) > 4 else ""
    primary_group = spec[5] if len(spec) > 5 else ""
    password = spec[6] if len(spec) > 6 else "?"
    group_specs = spec[7] if len(spec) > 7 else []

    return {
        "login": login,
        "email": email,
        "lastname": lastname,
        "firstname": firstname,
        "institution": institution,
        "primary_group": primary_group,
        "password": password,
        "groups": [_normalize_membership(entry) for entry in group_specs or []],
    }


def _normalize_membership(spec: Any) -> dict[str, str]:
    if isinstance(spec, dict):
        name = spec.get("name")
        if not name:
            raise ValueError("Group membership specification missing 'name'")
        return {"name": name, "role": spec.get("role", "M")}

    if isinstance(spec, str):
        return {"name": spec, "role": "M"}

    if not isinstance(spec, (list, tuple)) or not spec:
        raise ValueError("Invalid group membership specification")

    name = spec[0]
    role = spec[1] if len(spec) > 1 else "M"
    return {"name": name, "role": role}


# EOF
