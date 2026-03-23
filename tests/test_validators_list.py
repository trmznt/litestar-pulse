# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

import unittest

from litestar_pulse.lib import validators as v
from litestar_pulse.lib import formbuilder as fb


class TestListValidators(unittest.TestCase):
    def test_int_list_from_getall_values(self) -> None:
        validator = v.IntList(required=True, min_value=1, max_value=10)

        ok, err = validator.validate(["1", "2", "10"])
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertEqual(validator.transform(["1", "2", "10"]), [1, 2, 10])

    def test_int_list_rejects_out_of_range_item(self) -> None:
        validator = v.IntList(required=False, min_value=1, max_value=10)

        ok, err = validator.validate(["0", "2"])
        self.assertFalse(ok)
        self.assertIn("at least 1", err)

    def test_alphanum_list_rejects_invalid_item(self) -> None:
        validator = v.AlphanumList(required=False)

        ok, err = validator.validate(["abc123", "bad-value"])
        self.assertFalse(ok)
        self.assertIn("Invalid list item", err)
        self.assertIn("alphanumeric", err)

    def test_alphanumplus_list_accepts_plus_dash_dot_underscore(self) -> None:
        validator = v.AlphanumPlusList(required=True)

        ok, err = validator.validate(["abc+1", "x-y.z_2"])
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertEqual(
            validator.transform(["abc+1", "x-y.z_2"]), ["abc+1", "x-y.z_2"]
        )

    def test_uuid_list_rejects_invalid_uuid(self) -> None:
        validator = v.UUIDList(required=False)

        ok, err = validator.validate(
            [
                "9f2f7f67-7e57-4a5d-a2e8-bf85f9fb2b6e",
                "not-a-uuid",
            ]
        )
        self.assertFalse(ok)
        self.assertIn("Invalid list item", err)
        self.assertIn("valid UUID", err)

    def test_email_list_from_csv_string(self) -> None:
        validator = v.EmailList(required=True)

        ok, err = validator.validate("foo@example.org, bar@example.org")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertEqual(
            validator.transform("foo@example.org, bar@example.org"),
            ["foo@example.org", "bar@example.org"],
        )

    def test_required_list_rejects_empty_submission(self) -> None:
        validator = v.IntList(required=True)

        ok, err = validator.validate([])
        self.assertFalse(ok)
        self.assertEqual(err, "This field is required.")

        ok, err = validator.validate("")
        self.assertFalse(ok)
        self.assertEqual(err, "This field is required.")


class TestTomSelectEnumKeyCollectionField(unittest.TestCase):
    def test_field_instantiation(self) -> None:
        """Verify TomSelectEnumKeyCollectionField can be instantiated."""
        field = fb.TomSelectEnumKeyCollectionField(
            label="Test EnumKey Collection",
            category_key="@GROUP_ROLE",
            required=False,
        )

        self.assertEqual(field.label, "Test EnumKey Collection")
        self.assertFalse(field.required)
        self.assertIsNotNone(field.tom_select_options)
        self.assertTrue(callable(field.proxy_class))

    def test_field_with_custom_tom_select_options(self) -> None:
        """Verify TomSelectEnumKeyCollectionField accepts tom_select_options."""
        custom_opts = {"placeholder": "Select items..."}
        field = fb.TomSelectEnumKeyCollectionField(
            label="Custom Options",
            category_key="@GROUP_ROLE",
            required=True,
            tom_select_options=custom_opts,
        )

        self.assertEqual(field.tom_select_options, custom_opts)
        self.assertTrue(field.required)


if __name__ == "__main__":
    unittest.main()
