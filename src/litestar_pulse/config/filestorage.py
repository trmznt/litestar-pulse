import fsspec
import pathlib

from advanced_alchemy.types.file_object import FileObject, StoredObject, storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend

DB_DIR = pathlib.Path.cwd() / "db"
STORAGE_DIR = pathlib.Path.cwd() / "storage/lp"
TMP_UPLOAD_DIR = pathlib.Path.cwd() / "tmp_uploads"
LP_STORAGE = "lp_storage"


def init_filestorage() -> None:

    DB_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    TMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    local_fs = fsspec.filesystem("file", auto_mkdir=True)

    storages.register_backend(
        FSSpecBackend(
            fs=local_fs,
            key=LP_STORAGE,
            # This prepends the path to every file saved via this backend
            prefix=STORAGE_DIR.as_posix(),
        )
    )


# EOF
