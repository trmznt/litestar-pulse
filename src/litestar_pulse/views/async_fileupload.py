import json
import os
from pathlib import Path

import anyio
import fastnanoid

from litestar import (
    Controller,
    Request,
    Response,
    get,
    post,
    patch,
    delete,
    MediaType,
    head,
)

from litestar import (
    Controller,
    post,
    patch,
    delete,
    Request,
    Response,
    status_codes,
    exceptions,
)
from litestar.datastructures import FormMultiDict, UploadFile

from litestar.exceptions import HTTPException, NotFoundException
from litestar_pulse.lib.fileupload import generate_upload_id, get_upload_path
from litestar_pulse.config.filestorage import TMP_UPLOAD_DIR
from litestar_pulse.views.baseview import LPController


class AsyncFileUpload(LPController):

    path = "/async-fileupload"

    @post(name="init-upload")
    async def init_upload(self, request: Request) -> Response[str]:
        """
        Handles initial POST. If 'Upload-Length' header exists, it's a chunked start.
        Otherwise, it's a standard single-file upload.
        """
        # will receive Upload-Length header request
        # metadata in the body
        # need to return an upload_id in the text/plain response
        # upload_id = session_id-user_uuid/nanoid

        print("processing  init-upload")

        upload_length = request.headers.get("Upload-Length")
        upload_id = generate_upload_id(request)
        full_path = Path(TMP_UPLOAD_DIR) / get_upload_path(request) / upload_id
        # Ensure user/session directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if upload_length:
            # CHUNKED START: Create a placeholder file
            full_path.touch()
            return Response(
                content=upload_id,
                media_type=MediaType.TEXT,
                status_code=status_codes.HTTP_200_OK,
            )

        # SINGLE UPLOAD: Process file immediately
        data = await request.form()
        file: UploadFile | None = None
        for _key, value in data.multi_items():
            if isinstance(value, UploadFile):
                file = value
                break
        if file is None:
            raise exceptions.BadRequestException(
                "No upload file found in request body."
            )

        async with await anyio.open_file(full_path, "wb") as f:
            await f.write(await file.read())
        return Response(
            content=upload_id,
            media_type=MediaType.TEXT,
            status_code=status_codes.HTTP_200_OK,
        )

    @patch(path="/{upload_id:str}", name="patch-upload")
    async def patch_upload(self, upload_id: str, request: Request) -> Response:
        """Appends incoming chunks to the temporary file."""
        # will receive Content-Type, Upload-Offset, Upload-Name and Upload-Length headers
        # url will have upload_id, e.g. /async-fileupload/{upload_id}
        # check whether session_id matches the upload_id's session_id and user_uuid matches the upload_id's user_uuid

        # 1. Fetch FilePond Headers
        # headers are case-insensitive in Litestar

        print("processing patch-upload")

        if not upload_id:
            raise exceptions.BadRequestException("Missing upload_id in request.")

        try:
            offset = int(request.headers.get("Upload-Offset", 0))
            total_length = int(request.headers.get("Upload-Length", 0))
            original_name = request.headers.get("Upload-Name")
            content_type = request.headers.get("Content-Type")
        except ValueError:
            raise exceptions.BadRequestException("Invalid upload headers.")

        # 2. Check Content-Type (FilePond sends 'application/offset+octet-stream')
        if content_type != "application/offset+octet-stream":
            raise exceptions.UnsupportedMediaTypeException(
                "Invalid content type for chunk."
            )

        # 3. Verify File Integrity / Sequence
        upload_dir = anyio.Path(TMP_UPLOAD_DIR) / get_upload_path(request)
        temp_path = upload_dir / upload_id
        meta_path = upload_dir / f"{upload_id}.json"

        if not await temp_path.exists():
            raise exceptions.NotFoundException("Upload session not found.")

        # Get actual size on disk to ensure the offset matches
        current_size = (await temp_path.stat()).st_size
        if offset != current_size:
            # Conflict: Client is trying to send a chunk at the wrong position
            raise exceptions.HTTPException(
                detail=f"Offset mismatch. Expected {current_size}, got {offset}.",
                status_code=status_codes.HTTP_409_CONFLICT,
            )

        # 4. Handle Metadata (Upload-Name) - Option A
        if original_name and not await meta_path.exists():
            async with await anyio.open_file(meta_path, mode="w") as f:
                await f.write(
                    json.dumps({"filename": original_name, "total_size": total_length})
                )

        # 5. Process the Chunk Data
        chunk_data = await request.body()

        # Guard against overflow (ensuring we don't exceed total_length)
        if current_size + len(chunk_data) > total_length:
            raise exceptions.PayloadTooLargeException(
                "Chunk exceeds total file length."
            )

        async with await anyio.open_file(temp_path, mode="ab") as f:
            await f.seek(offset)
            await f.write(chunk_data)

        return Response(
            content=upload_id,
            media_type=MediaType.TEXT,
            status_code=status_codes.HTTP_200_OK,
        )

    @head(path="/{upload_id:str}", name="head-upload")
    async def head_upload(self, upload_id: str, request: Request) -> Response[None]:
        """
        Allows FilePond to resume an interrupted upload.
        Returns the current size of the temporary file.
        """
        # will receive Upload-Offset header request
        # url will have upload_id, e.g. /async-fileupload/{upload_id}
        # check whether session_id matches the upload_id's session_id and user_uuid matches the upload_id's user_uuid
        upload_dir = anyio.Path(TMP_UPLOAD_DIR) / get_upload_path(request)
        temp_path = upload_dir / upload_id
        # meta_path = upload_dir / f"{upload_id}.json"

        if not await temp_path.exists():
            return Response(content="", status_code=status_codes.HTTP_404_NOT_FOUND)

        # Get the current file size (the offset for the next chunk)
        file_size = (await temp_path.stat()).st_size

        return Response(
            status_code=status_codes.HTTP_200_OK,
            headers={"Upload-Offset": str(file_size)},
        )

    async def _delete_upload_id(self, upload_id: str, request: Request) -> None:
        placeholder_dir = anyio.Path(TMP_UPLOAD_DIR) / get_placeholder_path(request)
        temp_path = placeholder_dir / upload_id
        meta_path = placeholder_dir / f"{upload_id}.json"
        if await temp_path.exists():
            await temp_path.unlink()
        if await meta_path.exists():
            await meta_path.unlink()

    @delete(name="delete-upload")
    async def delete_upload(self, request: Request) -> Response[None]:
        """Handle FilePond default revert request: DELETE /async-fileupload with upload id in body."""
        upload_id = (await request.body()).decode().strip()
        if not upload_id:
            raise exceptions.BadRequestException("Missing upload id in request body.")
        await self._delete_upload_id(upload_id, request)
        return Response(content="", status_code=status_codes.HTTP_204_NO_CONTENT)

    @delete(path="/{upload_id:str}", name="delete-upload-by-id")
    async def delete_upload_by_id(
        self, upload_id: str, request: Request
    ) -> Response[None]:
        """
        Triggered when a user clicks 'undo' or 'remove' in FilePond.
        Deletes the temporary file from the server.
        """
        await self._delete_upload_id(upload_id, request)
        return Response(content="", status_code=status_codes.HTTP_204_NO_CONTENT)


# EOF
