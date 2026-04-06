FormBuilder Module Notes
========================

Overview
--------

The form system in src/litestar_pulse/lib/formbuilder.py is organized in three layers:

1. Field descriptors:
   InputField subclasses define schema, validator, and UI widget wiring.
2. Field proxies:
   _InputFieldProxy variants bind descriptors to a concrete ModelForm instance.
   They resolve current values/options and delegate validate/transform calls.
3. Model orchestration:
   ModelForm validates request data, transforms values, performs optimistic
   timestamp checks, and delegates persistence to service.update_from_dict().

Runtime Flow
------------

For update requests, the typical flow is:

1. ModelForm.transform_and_update(data, dbhandler)
2. ModelForm.check_timestamp() (optional)
3. ModelForm.transform() for typed/transformed payload
4. ModelForm.update() delegates to dbhandler service
5. Service.update_from_dict() applies model-specific hooks and persists

Key Behaviors
-------------

- List-like fields use validator type metadata and request.getall() when available.
- Async select options are populated through InputField.async_prerender hooks.
- File and FilePond field proxies preserve uploaded file objects or JSON payloads.

Consistency Rules
-----------------

- Optional select-like fields should treat empty input as None before int conversion.
- transform() should not mutate request data in-place.
- Debug prints should be avoided in library paths; use structured logging if needed.
- Keep per-field proxy get_value() behavior symmetric for both data and obj sources.

Streamlining Proposals
----------------------

1. Consolidate select proxy logic:
   _ForeignKeyInputFieldProxy, _EnumKeyInputFieldProxy, and _DBEnumKeyInputFieldProxy
   share nearly identical empty-value and text-resolution behavior and can be reduced
   to one base helper method.

2. Separate rendering script registration:
   TomSelect script assembly is duplicated in TomSelectField and
   TomSelectEnumKeyCollectionField. Consider one utility that receives field name
   and options.

3. Normalize flag processing:
   Move -retain-if-false!flag handling into a dedicated helper in ModelForm to keep
   transform() focused on validation/transform only.

4. Clarify field contract:
   Document, per InputField subclass, expected raw input shape and transformed output
   shape (scalar, tuple, list, uploaded file object, JSON payload).

5. Add focused tests for proxy edge cases:
   - empty string for optional enum/foreign key selects
   - FilePond JSON fallback behavior
   - transform() flag behavior without mutating input dict

Field Contract Summary
----------------------

These are the expected raw and transformed value shapes used by form proxies and validators:

- String-like fields (StringField, AlphanumField, EmailField, YAMLField):
   raw input is str, transformed output is scalar string.
- Numeric scalar fields (IntField, FloatField):
   raw input is str/int/float, transformed output is numeric scalar.
- Foreign key scalar fields (ForeignKeyField, DBEnumKeyField, EnumKeyField):
   raw input is id-like scalar or empty string, transformed output is int or None.
- Collection select fields (EnumKeyCollectionField, TomSelectEnumKeyCollectionField):
   raw input is list[str] or comma-separated str, transformed output is list[int].
- File fields (FileUploadField, MultipleFileUploadField):
   raw input is UploadedFile or list[UploadedFile], transformed output is proxy/file payload used by service layer.
- FilePond field (FilePondUploadField):
   raw input is upload identifier and companion JSON field, transformed output is JSON payload consumed in BaseView and service updates.

Implemented Streamlining Patch (Current)
----------------------------------------

The current cleanup in src/litestar_pulse/lib/formbuilder.py includes:

1. Shared select-proxy helpers in _InputFieldProxy:
   - _opts_with_option_callback()
   - _coerce_optional_int()
   - _resolve_related_text()

2. Refactor of duplicated logic in:
   - _ForeignKeyInputFieldProxy
   - _DBEnumKeyInputFieldProxy
   - _EnumKeyInputFieldProxy (optional int coercion reuse)

This reduces copy/paste branches while preserving existing return-value semantics
for each proxy type.

Additional Streamlining Implemented
-----------------------------------

1. TomSelect JavaScript registration was deduplicated into a single helper:
   _register_tomselect_jscode().

2. ModelForm transform flag processing was extracted into:
   ModelForm._apply_retain_if_false_flags().

3. Focused regression tests were added for:
   - proxy value handling for optional empty select values
   - transform flag behavior
   - TomSelect prerender script wiring

Suggested Test Targets
----------------------

- tests/test_formbuilder_proxy_values.py
- tests/test_formbuilder_transform_flags.py
- tests/test_formbuilder_tomselect_prerender.py
