# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations  # noqa: A005

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import asyncio
import base64

from passlib.context import CryptContext

password_crypt_context = CryptContext(schemes=["argon2"], deprecated="auto")


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
    return await asyncio.get_running_loop().run_in_executor(
        None, password_crypt_context.hash, password
    )


async def verify_password(plain_password: str | bytes, hashed_password: str) -> bool:
    """Verify Password.

    Args:
        plain_password (str | bytes): The string or byte password
        hashed_password (str): the hash of the password

    Returns:
        bool: True if password matches hash.
    """
    valid = await asyncio.get_running_loop().run_in_executor(
        None,
        password_crypt_context.verify,
        plain_password,
        hashed_password,
    )
    return bool(valid)


# EOF
