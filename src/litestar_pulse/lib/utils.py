# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from pathlib import Path


def resources_to_paths(resources: list[str]) -> list:
    """Convert a list of resources to a path string.

    Args:
        resources: A list of resource strings.

    Returns:
        A path string.
    """

    paths = []
    for resource in resources:
        if ":" in resource:
            module, directory = resource.split(":", 1)
            # import module, and get its __file__ attribute
            mod = __import__(module, fromlist=["__file__"])
            path = Path(mod.__file__).parent
            if directory:
                path = path / directory
            paths.append(path)
        else:
            paths.append(Path(resource))

    return paths


# EOF
