# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import unittest

from litestar_pulse.lib import formbuilder as fb


class _TransformFlagForm(fb.ModelForm):
    attachment = fb.StringField(label="Attachment", required=False)


class TestFormBuilderTransformFlags(unittest.TestCase):
    def test_retain_if_false_flag_drops_empty_attribute(self) -> None:
        form = _TransformFlagForm(obj=None, data={})
        request_data = {
            "attachment": "",
            "attachment-retain-if-false!flag": False,
        }

        transformed = form.transform(None, request_data)

        self.assertNotIn("attachment", transformed)

    def test_retain_if_false_flag_does_not_mutate_source_data(self) -> None:
        form = _TransformFlagForm(obj=None, data={})
        request_data = {
            "attachment": "",
            "attachment-retain-if-false!flag": False,
        }

        _ = form.transform(None, request_data)

        self.assertIn("attachment-retain-if-false!flag", request_data)
        self.assertFalse(request_data["attachment-retain-if-false!flag"])


if __name__ == "__main__":
    unittest.main()
