# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


# clean-room implementation of coretags based based on
# https://github.com/trmznt/rhombus/blob/master/rhombus/lib/tags.py

from typing import Any, Self
from markupsafe import Markup, escape

literal = Markup


class _SelfInstantiating(type):
    def __str__(cls):
        # Create a temp instance and return its string representation
        return str(cls())

    def __getitem__(cls, key):
        # Create a temp instance and return the result of its __getitem__
        return cls()[key]

    def __iadd__(cls, other):
        # Create instance, apply addition, and return the instance
        instance = cls()
        instance += other
        return instance


class htmltag(metaclass=_SelfInstantiating):
    """
    Base HTML element representation.

    Keyword arguments started with an underscore will not be used as attributes
    and instead will be used for internal purposes. For example, _register is used to
    determine whether an element should be registered in its container's elements
    dictionary.

    All other keyword arguments, including those suffixed with underscores will be set
    as attributes of the tag.
    """

    _newline: bool = False
    _main_container: bool = False

    def __init__(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        class_: str | None = None,
        _enabled: bool = True,
        _hidden: bool = False,
        _main_container: bool = False,
        _register: bool = True,
        **kwargs,
    ) -> Self:

        # we set name, id and class_ attributes if provided
        self.name = str(name).strip() if name else None
        self.id = str(id).strip() if id else self.name
        self.class_ = str(class_).strip() if class_ else None

        self.contents: list[htmltag | str] = []

        # this is the container for this instance
        self.container: htmltag | None = None

        # this holds all registered elements within this tag if this tag is a container
        self.elements: dict[str, htmltag] = {}

        self.enabled = _enabled
        self.hidden = _hidden
        self.main_container = _main_container
        self.register = _register

        self.attrs: dict[str, Any] = {}
        for key, val in kwargs.items():
            if key.startswith("_"):
                raise ValueError(
                    f"Argument '{key}' is not being consumed by internal process, please correct!"
                )
            key = key.lower()
            self.attrs[key.removesuffix("_")] = val

    def __repr__(self) -> str:
        return f"{self._tag}(name='{self.name or ''}', id='{self.id or ''}', class='{self.class_ or ''}')"

    def __str__(self) -> str:
        return str(self.__html__())  # pragma: no cover - convenience

    def add(self, *elements: Self | Markup | str) -> Self:
        """add and register htmltag elements"""
        for element in elements:
            if hasattr(element, "__tag__"):
                element = element.__tag__()
            self.contents.append(element)
            if isinstance(element, htmltag) and element.register:
                self.register_element(element)
        return self

    def __iadd__(self, element: Any) -> Self:
        self.add(element)
        return self

    def __getitem__(self, arg: Any) -> Self:
        if isinstance(arg, (tuple, list, set)):
            self.add(*list(arg))
        else:
            self.add(arg)
        return self

    def insert(self, index: int, *elements: Any) -> Self:
        for element in reversed(elements):
            self.contents.insert(index, element)
            self.register_element(element)
        return self

    def nonreg_add(self, *elements: Any) -> Self:
        """add htmltag elements without registering them"""
        for element in elements:
            self.contents.append(element)
        return self

    def attributes(self, attrs_only: bool = False) -> str:
        """Return serialized attribute string."""
        attrs: list[str] = []

        if not attrs_only:
            if self.id:
                id_attr = str(escape(self.id))
                attrs.append(f'id="{id_attr}"')
            if self.name:
                name_attr = str(escape(self.name))
                attrs.append(f'name="{name_attr}"')
            if self.class_:
                attrs.append(f'class="{escape(self.class_)}"')

        for key, val in self.attrs.items():
            safe_key = str(escape(key))
            if val is True:
                attrs.append(safe_key)
            elif val not in (None, False):
                safe_val = str(escape(val))
                attrs.append(f'{safe_key}="{safe_val}"')

        return " ".join(attrs)

    def opts(self, **kwargs: Any) -> Self:
        """Set additional attributes for this tag."""
        for key, val in kwargs.items():
            if key.startswith("_"):
                raise ValueError(
                    f"Argument '{key}' is not being consumed by internal process, please correct!"
                )
            key = key.lower()
            self.attrs[key.removesuffix("_")] = val
        return self

    @property
    def _tag(self):
        return self.__class__.__name__.lower()

    def __html__(self) -> Markup:
        return self.r()

    # container methods

    def get_container(self) -> Self:
        return self.container.get_container() if self.container else self

    def __contains__(self, identifier: str) -> bool:
        return identifier in self.elements

    def register_element(self, element: Any) -> None:
        """Register an element within this tag's elements dictionary."""

        # Only register if it's an htmltag and not a main container.
        # Main containers are not registered to avoid conflicts.
        if not isinstance(element, htmltag) or element.main_container is True:
            return

        # If the element is already set as a main container, we skip registration
        # to avoid conflicts.
        if element._main_container:
            return

        container = self.get_container()
        element.container = self

        def _register(target: htmltag, node: htmltag) -> None:
            if ident := node.id:
                existing = target.elements.get(ident)
                if existing is not None and existing is not node:
                    raise ValueError(
                        f"Element with id '{ident}' is already registered in this container."
                    )
                target.elements[ident] = node

            for child in node.elements.values():
                _register(target, child)

        _register(self, element)
        if container is not self:
            _register(container, element)

    def get_element(self, identifier: str) -> htmltag:
        """Retrieve a registered element by its identifier."""
        return self.elements[identifier]


class element(htmltag):
    """non-tag container HTML element representation."""

    def r(self) -> Markup:
        """Render this element into an HTML string."""
        return Markup(
            "\n".join(
                content.__html__() if hasattr(content, "__html__") else escape(content)
                for content in self.contents
            )
        )


class singletag(htmltag):
    """Minimal HTML single element representation."""

    def r(self) -> Markup:
        """Render this tag into an HTML string."""
        attrs = self.attributes()
        attrs_part = f" {attrs}" if attrs else ""
        return Markup(f"<{self._tag}{attrs_part} />{'\n' if self._newline else ''}")


class pairedtag(htmltag):
    """Minimal HTML paired element representation."""

    def r(self) -> Markup:
        """Render this tag into an HTML string."""
        attrs = self.attributes()
        attrs_part = f" {attrs}" if attrs else ""
        inner_html = "".join(
            content.__html__() if hasattr(content, "__html__") else escape(content)
            for content in self.contents
        )
        return Markup(
            f"<{self._tag}{attrs_part}>{inner_html}</{self._tag}>{'\n' if self._newline else ''}"
        )


# generate a list of singletag and pairedtag classes for all HTML tags
_single_tags = [
    "img",
    "input",
    "br",
    "hr",
    "meta",
    "link",
    "source",
    "track",
    "wbr",
    "param",
    "col",
    "embed",
    "area",
    "base",
]
for tag in _single_tags:
    globals()[tag] = type(tag, (singletag,), {})

_paired_tags = [
    "div",
    "span",
    "p",
    "a",
    "b",
    "i",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "form",
    "label",
    "button",
    "textarea",
    "select",
    "option",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "nav",
    "footer",
    "header",
    "section",
    "article",
    "aside",
    "dl",
    "dt",
    "dd",
    "fieldset",
    "legend",
    "pre",
    "code",
    "blockquote",
    "html",
    "head",
    "body",
    "time",
]
for tag in _paired_tags:
    globals()[tag] = type(tag, (pairedtag,), {})


# special cases


class li(pairedtag):
    pass


class ul(pairedtag):

    def add(self, *args: Any) -> Self:
        for arg in args:
            if not isinstance(arg, li):
                raise ValueError("UL/OL should only have LI content")
            super().add(arg)
        return self


class ol(ul):
    pass


# EOF
