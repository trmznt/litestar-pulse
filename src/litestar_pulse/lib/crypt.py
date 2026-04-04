# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations  # noqa: A005

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import asyncio
import base64

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hasher = PasswordHash.recommended()


def _coerce_password_input(password: str | bytes) -> str:
    """Normalize password input for pwdlib APIs."""

    if isinstance(password, bytes):
        return password.decode()
    return password


def get_encryption_key(secret: str) -> bytes:
    """Get Encryption Key.

    Args:
        secret (str): Secret key used for encryption

    Returns:
        bytes: a URL safe encoded version of secret
    """
    if len(secret) <= 32:
        secret = f"{secret:<32}"[:32]
    return base64.urlsafe_b64encode(secret.encode())


async def hash_password(password: str | bytes) -> str:
    """Get password hash.

    Args:
        password: Plain password
    Returns:
        str: Hashed password
    """
    return await asyncio.to_thread(
        password_hasher.hash, _coerce_password_input(password)
    )


async def verify_password(plain_password: str | bytes, hashed_password: str) -> bool:
    """Verify Password.

    Args:
        plain_password (str | bytes): The string or byte password
        hashed_password (str): the hash of the password

    Returns:
        bool: True if password matches hash.
    """
    plain = _coerce_password_input(plain_password)

    try:
        valid = await asyncio.to_thread(password_hasher.verify, plain, hashed_password)
    except (UnknownHashError, ValueError):
        return False

    return bool(valid)


# EOF
