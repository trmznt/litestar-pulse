# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import unittest

from tagato import tags as t

from litestar_pulse.lib import formbuilder as fb


class _TomSelectForm(fb.ModelForm):
    simple = fb.TomSelectField(label="Simple")
    roles = fb.TomSelectEnumKeyCollectionField(label="Roles", category_key="@ROLES")

    async def set_layout(self, controller=None) -> t.Tag:
        return t.fragment()[self.simple, self.roles]


class TestFormBuilderTomSelectPrerender(unittest.IsolatedAsyncioTestCase):
    async def test_tomselect_fields_register_init_scripts(self) -> None:
        form = _TomSelectForm(obj=None, data={})

        await form.async_prerender(controller=None)

        self.assertEqual(len(form.jscode), 2)
        self.assertTrue(
            all("new TomSelect(element" in script for script in form.jscode)
        )
        self.assertTrue(any('"maxItems": null' in script for script in form.jscode))


if __name__ == "__main__":
    unittest.main()
