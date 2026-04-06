# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import importlib.resources
from pathlib import Path
from typing import Dict, Any, Optional

from mako.lookup import TemplateLookup

from litestar import response, get, Request
from litestar.enums import MediaType
from litestar.contrib.mako import MakoTemplateEngine
from litestar.template.config import TemplateConfig


# context injector

__context_injector__ = []


# generate a decorator function that injects context into the template rendering function
def context_injector(func):
    global __context_injector__
    __context_injector__.append(func)


class Template(response.Template):
    def __init__(self, **kwargs):

        for func in __context_injector__:
            func(kwargs["context"])

        # Force the media type to HTML regardless of filename
        kwargs.setdefault("media_type", MediaType.HTML)
        super().__init__(**kwargs)


def render_to_response(
    template_name: str,
    context: dict[str, object] | None = None,
    status_code: int = 200,
) -> response.Template:
    return Template(
        template_name=template_name, context=context or {}, status_code=status_code
    )


# 1. ENHANCED LOOKUP: Handles Asset Specs and Global Overrides
class PyramidStyleLookup(TemplateLookup):
    def __init__(self, *args, **kwargs):
        # Dictionary for GLOBAL overrides (set at startup)
        self.global_overrides: Dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def override_asset(self, to_override: str, override_with: str):
        """Mimics Pyramid's global config.override_asset()"""
        self.global_overrides[to_override] = override_with

    def adjust_uri(self, uri: str, relateto: Optional[str] = None) -> str:
        # Step A: Apply Global Overrides first
        uri = self.global_overrides.get(uri, uri)

        # Step B: Resolve Asset Specification (package:path)
        if ":" in uri and not uri.startswith(("/", "http")):
            package, path = uri.split(":", 1)
            try:
                with importlib.resources.path(package, "") as pkg_path:
                    return str((pkg_path / path).resolve())
            except (ImportError, FileNotFoundError):
                pass

        return super().adjust_uri(uri, relateto)


# 2. DYNAMIC DEPENDENCY: Handles Per-Request Overrides (Themes/AB Testing)
async def get_request_overrides(request: Request) -> Dict[str, str]:
    # Logic for dynamic selection
    theme = request.query_params.get("theme", "default_theme")
    is_beta = request.cookies.get("version") == "beta"

    return {
        "layout": f"{theme}:base.mako",
        "header": "my_app:new_header.mako" if is_beta else "my_app:old_header.mako",
    }


def example():

    from litestar import Litestar

    # 3. INITIALIZATION
    my_lookup = PyramidStyleLookup(
        directories=["./templates"], module_directory="./mako_cache"
    )

    # --- GLOBAL OVERRIDES (Startup) ---
    # Swap out a 3rd party template for your own version globally
    my_lookup.override_asset("auth_lib:login.mako", "my_app:custom_login.mako")

    app = Litestar(
        route_handlers=[...],
        dependencies={"req_overrides": get_request_overrides},
        template_config=TemplateConfig(
            engine=MakoTemplateEngine,
            engine_instance=MakoTemplateEngine(engine_instance=my_lookup),
            # Global variables (renderer_globals)
            instance_context={"h": lambda x: x.upper()},
        ),
    )

    # 4. ROUTE HANDLER
    @get("/")
    def home(req_overrides: Dict[str, str]) -> Template:
        return Template(
            template_name="my_app:home.mako",
            context={"overrides": req_overrides},  # Pass dynamic overrides to Mako
        )


# EOF
