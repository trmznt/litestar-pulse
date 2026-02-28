# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
from datetime import timedelta

from litestar.logging import LoggingConfig
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.contrib.mako import MakoTemplateEngine
from litestar.response import Template
from litestar.template.config import TemplateConfig
from litestar.plugins.flash import FlashConfig


from litestar_pulse.lib.utils import resources_to_paths

# Define your config
logging_config = LoggingConfig(
    root={"level": "INFO", "handlers": ["queue_listener"]},
    disable_stack_trace={404},
)

# Define template config
template_config = TemplateConfig(
    directory=resources_to_paths(["litestar_pulse:templates"]),
    engine=MakoTemplateEngine,
)

# Define flash config
flash_config = FlashConfig(template_config=template_config)

# Use the .configure() method to get a logger factory
logger = logging_config.configure()("litestar-pulse")

session_config = ServerSideSessionConfig()

# EOF
