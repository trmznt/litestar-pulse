# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import unittest

from litestar_pulse.lib import formbuilder as fb


class _ValidationForm(fb.ModelForm):
    required_name = fb.StringField(label="Name", required=True)
    optional_desc = fb.StringField(label="Description", required=False)


class TestFormBuilderValidateTransformConsistency(unittest.TestCase):
    def test_validate_checks_missing_required_fields(self) -> None:
        form = _ValidationForm(obj=None, data={})

        with self.assertRaises(fb.ParseFormError):
            form.validate(None, {})

    def test_transform_only_processes_present_fields(self) -> None:
        form = _ValidationForm(obj=None, data={})

        transformed = form.transform(None, {"optional_desc": "hello"})

        self.assertEqual(transformed, {"optional_desc": "hello"})
        self.assertNotIn("required_name", transformed)


if __name__ == "__main__":
    unittest.main()
