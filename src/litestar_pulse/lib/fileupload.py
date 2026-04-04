# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

# file upload utilities

from typing import Any, TYPE_CHECKING

import json
import fastnanoid

from litestar_pulse.config.filestorage import TMP_UPLOAD_DIR
from litestar_pulse.lib.utils import get_request_session_id

if TYPE_CHECKING:
    from litestar import Request

from dataclasses import dataclass


def get_upload_path(request: Request) -> str:
    """
    Generates a placeholder path for the upload based on the user and session.
    The placeholder path is structured as "{session_id}-{user_uuid}" to ensure
    uniqueness across sessions and users and that both session id and user uuid
    are valid.
    """
    user = request.user
    if not user:
        raise ValueError("User must be authenticated to generate placeholder path.")

    session_id = get_request_session_id(request)
    if not session_id:
        raise ValueError("Session ID is missing; cannot map uploads to a session.")
    uuid = user.uuid
    return f"{session_id}-{uuid}"


def generate_upload_id(request: Request) -> str:
    return f"{fastnanoid.generate()}-upload"


@dataclass
class FileUploadProxy:
    upload_id: str
    path: str
    filename: str
    is_new_upload: bool = False
    selected: bool = True
    description: str = ""
    category: str = ""

    def __init__(
        self,
        upload_id: str,
        filename: str,
        request: Request,
        selected: bool = True,
        description: str = "",
        category: str = "",
    ):
        self.upload_id = upload_id
        self.filename = filename
        self.selected = bool(selected)
        self.description = description or ""
        self.category = category or ""
        self.is_new_upload = upload_id.endswith("-upload")
        if self.is_new_upload:
            # this is a new upload files
            self.path = (
                TMP_UPLOAD_DIR / f"{get_upload_path(request)}/{upload_id}"
            ).as_posix()
        else:
            # this is an existing file reference, path is same as upload_id
            self.path = None

    def set_path_from_instance(self, instance: Any) -> None:
        if not self.is_new_upload and self.path is None:
            self.path = instance.get_fileobject_path(self.upload_id)


# EOF
