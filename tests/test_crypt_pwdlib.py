# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import unittest

from litestar_pulse.lib import crypt


class TestCryptPwdlib(unittest.IsolatedAsyncioTestCase):
    async def test_hash_and_verify_with_str_password(self) -> None:
        hashed = await crypt.hash_password("secret123")

        self.assertTrue(await crypt.verify_password("secret123", hashed))
        self.assertFalse(await crypt.verify_password("wrong", hashed))

    async def test_hash_and_verify_with_bytes_password(self) -> None:
        hashed = await crypt.hash_password(b"secret-bytes")

        self.assertTrue(await crypt.verify_password(b"secret-bytes", hashed))
        self.assertFalse(await crypt.verify_password(b"wrong", hashed))

    async def test_verify_returns_false_for_invalid_hash(self) -> None:
        self.assertFalse(await crypt.verify_password("secret", "not-a-valid-hash"))


if __name__ == "__main__":
    unittest.main()
