from __future__ import annotations

from urllib.parse import urlencode

from browser import ajax, document, window  # type: ignore


def _checkboxes(tag_id: str):
    return document.select(f'input[name="{tag_id}"]')


def _set_checkbox_state(tag_id: str, value: bool | None) -> None:
    for checkbox in _checkboxes(tag_id):
        if value is None:
            checkbox.checked = not checkbox.checked
        else:
            checkbox.checked = value


def _serialize_form(form, button) -> str:
    pairs: list[tuple[str, str]] = []
    for element in form.elements:
        name = getattr(element, "name", None)
        if not name or getattr(element, "disabled", False):
            continue
        element_type = (getattr(element, "type", "") or "").lower()
        if element_type in {"checkbox", "radio"} and not getattr(
            element, "checked", False
        ):
            continue
        if element_type in {"submit", "button", "file"}:
            continue
        tag_name = (getattr(element, "tagName", "") or "").lower()
        if tag_name == "select" and getattr(element, "multiple", False):
            for option in getattr(element, "options", []):
                if getattr(option, "selected", False):
                    value = getattr(option, "value", getattr(option, "text", ""))
                    pairs.append((name, value))
            continue
        pairs.append((name, getattr(element, "value", "")))

    button_name = getattr(button, "name", None)
    if button_name:
        pairs.append((button_name, getattr(button, "value", "")))
    return urlencode(pairs, doseq=True)


def _bind_click(element_id: str, handler) -> None:
    node = document.getElementById(element_id)
    if node is None:
        return
    node.bind("click", handler)


def _handle_submit(prefix: str, event) -> None:
    event.preventDefault()
    button = event.currentTarget
    form = getattr(button, "form", None)
    if form is None:
        return

    body = _serialize_form(form, button)

    def _on_complete(req):
        if 200 <= req.status < 300:
            modal = document.getElementById(f"{prefix}-modal")
            if modal:
                modal.innerHTML = req.text
                bootstrap = getattr(window, "bootstrap", None)
                if bootstrap and hasattr(bootstrap, "Modal"):
                    bootstrap.Modal.getOrCreateInstance(modal).show()
                else:
                    modal.classList.add("show")
                    modal.style.display = "block"
        else:
            window.console.error("Selection bar request failed", req.status)

    req = ajax.ajax()
    req.bind("complete", _on_complete)
    req.open(
        getattr(form, "method", "POST") or "POST", getattr(form, "action", ""), True
    )
    req.set_header("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8")
    req.set_header("X-Requested-With", "XMLHttpRequest")
    req.send(body)


def register_selection_bar(prefix: str, tag_id: str) -> None:
    def _make_handler(value: bool | None):
        def handler(event):
            event.preventDefault()
            _set_checkbox_state(tag_id, value)

        return handler

    _bind_click(f"{prefix}-select-all", _make_handler(True))
    _bind_click(f"{prefix}-select-none", _make_handler(False))
    _bind_click(f"{prefix}-select-inverse", _make_handler(None))
    _bind_click(f"{prefix}-submit-delete", lambda event: _handle_submit(prefix, event))


__all__ = ["register_selection_bar"]
