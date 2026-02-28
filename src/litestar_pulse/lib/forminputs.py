# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from collections.abc import Callable, Awaitable
from typing import Any, TYPE_CHECKING, Self

from markupsafe import Markup, escape

from . import coretags as t
from .validators import Validator

if TYPE_CHECKING:
    from .formbuilder import InputField

fieldset = t.fieldset
legend = t.legend


class FormField:
    def __init__(
        self, id: str, field_type: str, label: str | None = None, required: bool = False
    ):
        self.id = id
        self.field_type = field_type
        self.label = label or id.capitalize()
        self.required = required


class FieldDTO:
    pass


class HTMLForm(t.pairedtag):

    _tag: str = "form"
    _newline: bool = True
    _main_container: bool = True

    def __init__(
        self,
        *,
        action: str = "",
        method: str = "post",
        enctype: str = "application/x-www-form-urlencoded",
        _readonly: bool = False,
        **kwargs: dict,
    ) -> None:
        super().__init__(action=action, method=method, enctype=enctype, **kwargs)
        self.readonly = _readonly
        self.scriptlinks: list[str] = []
        self.jscode: list[str] = []
        self.pyscode: list[str] = []

    async def async_preprocess(self) -> None:
        for element in self.elements.values():
            if hasattr(element, "async_preprocess"):
                await element.async_preprocess()


class InlineInput(t.div):
    _tag = "div"

    def __init__(self, **kwargs):
        super().__init__(class_="row g-3 align-items-center mb-3", **kwargs)


class BaseInput(t.singletag):

    _tag = "input"
    _type = "text"

    def __init__(
        self,
        *,
        _validator: Validator | None = None,
        _inputfield: InputField | None = None,
        name: str | None = None,
        _label: str | None = None,
        value: Any = None,
        _update_dict: dict | None = None,
        placeholder: str = "",
        _info: str = "",
        _size: int = 3,
        _offset: int = 2,
        _extra_control: str = "",
        _readonly: bool | None = None,  # if None, follow container
        style: str = "",
        _popover: str = "",
        _error: str = "",
        **kwargs: dict,
    ) -> None:
        self.inputfield = _inputfield
        self.validator = _validator
        self.label = _label or name
        name = name or (
            _inputfield.name
            if _inputfield
            else (_validator._name if _validator else None)
        )
        super().__init__(name=name, **kwargs)

        self.readonly = _readonly

        self.value = value
        self.update_dict = _update_dict
        self.placeholder = placeholder
        self.error = _error
        self.info = _info
        self.size = _size
        self.offset = _offset
        self._extra_control = _extra_control or ""
        self.readonly = _readonly
        self._style = style
        self.popover = _popover

    # accessor

    def get_value(self) -> str | tuple[int | str, str] | bool | None:
        if self.update_dict is not None:
            val = self.update_dict.get(self.name, None)
            if val is not None:
                return val
        if self.inputfield is not None and self.value is None:
            return self.inputfield.get_value()
        if self.validator is not None and self.value is None:
            return self.validator.get_value()
        return (
            self.value
            if self.value is not None
            else "get_value() is None, needs to be recoded"
        )

    def is_readonly(self) -> bool:
        if self.readonly is not None:
            return self.readonly
        return self.get_container().readonly

    def opts(self, **kwargs: Any) -> Self:

        if "_size" in kwargs:
            self.size = kwargs.pop("_size")
        if "_offset" in kwargs:
            self.offset = kwargs.pop("_offset")
        if "_error" in kwargs:
            self.error = kwargs.pop("_error")
        if "_info" in kwargs:
            self.info = kwargs.pop("_info")

        return super().opts(**kwargs)

    # CSS classes and styles

    def class_value(self) -> str:
        classes = ["col-sm-2", "col-form-label"]
        return " ".join(classes)

    def class_value(self, size=None):
        col = self.size if size is None else size
        col = col or 12
        return f"col-12 col-md-{col} ps-md-2"

    def class_label(self):
        return f"col-md-{self.offset} col-form-label text-end align-self-start pt-2 ps-1 pe-0"

    def class_input(self):
        base = "form-control ps-2 pe-2"
        return base + (" is-invalid" if self.error else "")

    def class_div(self):
        return "mb-3"

    def style(self):
        return self._style  # or "width:100%"

    # additional text elements

    def error_text(self):
        if not self.error:
            return ""
        return t.span(class_="invalid-feedback")[self.error]

    def info_text(self):
        if not self.info:
            return ""
        if self.info.startswith("popup:"):
            url = escape(self.info[6:])
            return Markup(
                '<div class="col-auto d-flex align-items-center">'
                f'<a class="js-newWindow text-decoration-none" data-popup="width=400,height=200,scrollbars=yes" href="{url}" aria-label="More info">'
                '<span class="fw-semibold">?</span>'
                "</a></div>"
            )
        return Markup(
            f'<small class="form-text text-muted">{escape(self.info)}</small>'
        )

    def render_label(self) -> Markup | t.htmltag:

        pop_title = pop_content = ""
        if self.popover:
            pop_title = self.label or ""
            pop_content = self.popover

        return (
            t.label(
                class_=self.class_label(),
                for_=self.name,
                **{
                    "data-bs-toggle": "popover",
                    "data-bs-placement": "top",
                    "data-bs-title": pop_title,
                    "data-bs-content": pop_content,
                },
            )[escape(self.label)]
            if self.label is not None
            else ""
        )

    def render_input(self, value=None) -> Markup | t.htmltag:
        if self.error:
            input_class = "form-control is-invalid"
        else:
            input_class = "form-control"

        readonly = self.is_readonly()

        # food for thought: <input type="text" readonly class="form-control-plaintext">
        # will render a readonly input as plain text (no boxes nor decorations)

        return t.div(class_=self.class_value())[
            t.input(
                type=self._type,
                id=self.id,
                name=self.name,
                value=escape(value if value is not None else self.get_value()),
                class_=self.class_input(),
                placeholder=self.placeholder,
                style=self.style(),
                readonly=readonly,
            ),
            self.error_text(),
        ]

    def r(self) -> Markup:

        elements = t.element()[
            self.render_label(),
            self.render_input(),
            self.info_text(),
        ]

        return self.div_wrap(elements.r())

    def div_wrap(self, markup) -> Markup:
        if not isinstance(self.container, InlineInput):
            return t.div(class_="row g-3 align-items-center mb-3")[markup].r()
        return markup


class HiddenInput(BaseInput):
    _type = "hidden"

    def r(self) -> Markup:
        return t.input(
            type=self._type, id=self.id, name=self.name, value=escape(self.get_value())
        ).r()


class TextInput(BaseInput):
    _type = "text"


class PasswordInput(BaseInput):
    _type = "password"


class EmailInput(BaseInput):
    _type = "email"


class CheckboxInput(BaseInput):
    _type = "checkbox"

    def get_value(self) -> bool:
        val = super().get_value()
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    def render_input(self, value=None) -> Markup | t.htmltag:
        readonly = self.is_readonly()

        if readonly:
            if self.get_value():
                return t.div(class_=self.class_value())[
                    t.span(class_="badge text-bg-success border border-success")[
                        t.i(class_="bi bi-check-lg me-1"), self.label
                    ]
                ]
            return t.div(class_=self.class_value())[
                t.span(
                    class_="badge bg-secondary-subtle text-body-tertiary border border-secondary-subtle"
                )[
                    t.i(class_="bi bi-x-circle text-muted me-1", title="Disabled"),
                    self.label,
                ]
            ]

        checked = True if self.get_value() else None
        return t.div(class_=self.class_value())[
            t.div(class_="form-check form-check-inline")[
                t.input(type="hidden", name=self.name, _register=False, value="off"),
                t.input(
                    type=self._type,
                    id=self.id,
                    name=self.name,
                    value="on",
                    checked=checked,
                    readonly=False,
                    class_="form-check-input",
                ),
                t.label(class_="form-check-label", for_=self.name)[escape(self.label)],
            ]
        ]

    def render_label(self) -> Markup | t.htmltag:

        if self.is_readonly():
            # label is rendered as part of the badge in render_input when readonly
            return Markup("")

        return t.label(class_="form-check-label", for_=self.name)[escape(self.label)]

    def r(self) -> Markup:

        # checkbox is a special case where the label is rendered after the input,
        # hence label is not rendered in render_label() but in render_input()

        elements = self.render_input()
        return elements.r()

        return self.div_wrap(elements.r())


class CheckboxGroupInput(BaseInput):
    _type = None  # type is determined by individual checkboxes

    # this class renders a group of checkboxes, each with its own label and value,
    # but all sharing the same name (as a list)

    def render_label(self):
        return super().render_label()

    def render_input(self, value=None) -> Markup | t.htmltag:
        return t.element()[
            *[item.r() for item in self.contents if isinstance(item, CheckboxInput)]
        ]


class SelectInput(BaseInput):

    def __init__(
        self,
        _options: list[tuple[str, str]] | None = None,
        _option_callback: Callable[[], Awaitable[list[tuple[str, str]]]] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.options = _options or []
        self.option_callback = _option_callback

    def class_input(self):
        base = "form-select ps-2 pe-2"
        return base + (" is-invalid" if self.error else "")

    def render_input(self) -> Markup | t.htmltag:

        readonly = self.is_readonly()
        value = self.get_value()

        if value is None:
            value = ("", "")
        elif isinstance(value, str):
            value = (value, value)

        if readonly:
            return super().render_input(value=value[1])

        if not any(self.options):
            raise RuntimeError(
                "SelectInput requires calling to async_preprocess to populate options"
            )

        select_tag = t.select(
            id=self.id,
            name=self.name,
            class_=self.class_input(),
            style=self.style(),
            disabled=readonly,
        )[
            [
                t.option(value=val, selected=(val == value[0]))[text]
                for val, text in self.options
            ]
        ]

        return t.div(class_=self.class_value())[select_tag, self.error_text()]

    async def async_preprocess(self) -> None:
        if self.option_callback is not None:
            print("Fetching options for SelectInput...")
            self.options = await self.option_callback()
            if self.inputfield and not self.inputfield.input_field.required:
                self.options = [("", "")] + self.options


class EnumKeyInput(SelectInput):
    _type = "text"

    async def async_preprocess(self) -> None:
        # do nothing, options are set in render_input() without the need to do async call
        pass

    def get_value_XXX(self) -> tuple[int, str]:
        id_key, enumkey = super().get_value()
        return id_key, enumkey

    def render_input(self) -> Markup | t.htmltag:
        self.options = (self.inputfield or self.validator).get_options()
        return super().render_input()


class TomSelectInput(SelectInput):
    """This is a select input specific for Tom-select JS library"""

    def __init__(self, url_source: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.url_source = url_source

    def render_input(self):
        return super().render_input()


# EOF
