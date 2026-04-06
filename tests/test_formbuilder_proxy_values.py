# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import unittest

from litestar_pulse.lib import formbuilder as fb


class _ProxyValueForm(fb.ModelForm):
    fk_field = fb.ForeignKeyField(label="FK", required=False, foreignkey_for="group")
    enum_field = fb.EnumKeyField(label="Enum", required=False)
    db_enum_field = fb.DBEnumKeyField(label="DBEnum", required=False)


class TestFormBuilderProxyValues(unittest.TestCase):
    def test_optional_select_empty_values_do_not_raise(self) -> None:
        form = _ProxyValueForm(
            obj=None,
            data={
                "fk_field": "",
                "enum_field": "",
                "db_enum_field": "",
            },
        )

        self.assertEqual(form.fk_field.get_value(), (None, ""))
        self.assertEqual(form.enum_field.get_value(), (None, None))
        self.assertEqual(form.db_enum_field.get_value(), (None, None))


if __name__ == "__main__":
    unittest.main()
