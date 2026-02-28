from __future__ import annotations

# how to use:
# include this module in the template via PyScript
# (<py-script src=".../selection_bar.py"></py-script>)
# and call await setup_selection_bar(prefix, tag_id)
# after rendering the toolbar to activate the behaviors.

import asyncio
import inspect
from typing import Any, Callable

from js import URLSearchParams, console, document, fetch, window  # type: ignore
from pyodide.ffi import create_proxy

_EVENT_PROXIES: list[Any] = []


def _iter_checkboxes(tag_id: str):
    nodes = document.querySelectorAll(f'input[name="{tag_id}"]')
    length = nodes.length
    for index in range(length):
        yield nodes.item(index)


def _serialize_form(form, *, extra_name: str | None = None, extra_value: str = ""):
    params = URLSearchParams.new()
    elements = form.elements
    length = elements.length
    for index in range(length):
        field = elements.item(index)
        name = getattr(field, "name", None)
        if not name or getattr(field, "disabled", False):
            continue
        field_type = (getattr(field, "type", "") or "").lower()
        if field_type in {"checkbox", "radio"} and not getattr(field, "checked", False):
            continue
        if field_type == "submit":
            continue
        params.append(name, getattr(field, "value", ""))
    if extra_name:
        params.set(extra_name, extra_value)
    return params


def _wait_for_dom_ready() -> asyncio.Future[Any] | None:
    if document.readyState != "loading":
        return None

    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()

    def _resolve(_event):
        if not future.done():
            future.set_result(None)

    proxy = create_proxy(_resolve)
    _EVENT_PROXIES.append(proxy)
    document.addEventListener("DOMContentLoaded", proxy, {"once": True})
    return future


def _bind(prefix: str, suffix: str, handler: Callable[[Any], Any]) -> None:
    node = document.getElementById(f"{prefix}-{suffix}")
    if node is None:
        return

    if inspect.iscoroutinefunction(handler):

        def callback(event):
            asyncio.create_task(handler(event))

    else:
        callback = handler

    proxy = create_proxy(callback)
    _EVENT_PROXIES.append(proxy)
    node.addEventListener("click", proxy)


def register_selection_bar(prefix: str, tag_id: str) -> None:
    def handle_select(value: bool | None):
        boxes = list(_iter_checkboxes(tag_id))
        if value is None:
            for checkbox in boxes:
                checkbox.checked = not getattr(checkbox, "checked", False)
            return
        for checkbox in boxes:
            checkbox.checked = value

    def on_select_all(event):
        event.preventDefault()
        handle_select(True)

    def on_select_none(event):
        event.preventDefault()
        handle_select(False)

    def on_select_inverse(event):
        event.preventDefault()
        handle_select(None)

    async def on_submit_delete(event):
        event.preventDefault()
        button = event.currentTarget
        form = getattr(button, "form", None)
        if form is None:
            console.warn("Selection bar submit button has no form reference")
            return

        params = _serialize_form(
            form,
            extra_name=getattr(button, "name", None),
            extra_value=getattr(button, "value", ""),
        )

        try:
            response = await fetch(
                form.action,
                {
                    "method": getattr(form, "method", "POST") or "POST",
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    "body": params,
                },
            )
        except Exception as exc:  # pragma: no cover - network errors
            console.error("Selection bar request failed", exc)
            return

        text = await response.text()
        modal = document.getElementById(f"{prefix}-modal")
        if modal is not None:
            modal.innerHTML = text
            bootstrap = getattr(window, "bootstrap", None)
            if bootstrap and hasattr(bootstrap, "Modal"):
                bootstrap.Modal.getOrCreateInstance(modal).show()
            else:
                modal.classList.add("show")
                modal.style.display = "block"

    _bind(prefix, "select-all", on_select_all)
    _bind(prefix, "select-none", on_select_none)
    _bind(prefix, "select-inverse", on_select_inverse)
    _bind(prefix, "submit-delete", on_submit_delete)


async def setup_selection_bar(prefix: str, tag_id: str) -> None:
    wait_future = _wait_for_dom_ready()
    if wait_future is not None:
        await wait_future
    register_selection_bar(prefix, tag_id)


__all__ = ["register_selection_bar", "setup_selection_bar"]
