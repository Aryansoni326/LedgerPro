"""
Server-side upload validation: extension whitelist, size cap, and magic-byte sniffing.
"""
import os
from typing import BinaryIO

# 10 MB default cap (matches client-side limit)
DEFAULT_MAX_BYTES = 10 * 1024 * 1024

DOCUMENT_EXTENSIONS = frozenset({'.pdf', '.jpg', '.jpeg', '.png'})
STUB_EXTENSIONS = frozenset({'.pdf', '.jpg', '.jpeg', '.png', '.xlsx'})

# Magic-byte signatures per extension (first bytes of file content)
_MAGIC: dict[str, tuple[bytes, ...]] = {
    '.pdf': (b'%PDF',),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.xlsx': (b'PK\x03\x04',),  # Office Open XML (ZIP container)
}


class UploadValidationError(Exception):
    """Raised when an uploaded file fails server-side validation."""


def _extension(filename: str) -> str:
    return os.path.splitext(filename or '')[1].lower()


def _matches_magic(header: bytes, ext: str) -> bool:
    signatures = _MAGIC.get(ext, ())
    if not signatures:
        return True
    return any(header.startswith(sig) for sig in signatures)


def read_limited(file_obj: BinaryIO, max_bytes: int = DEFAULT_MAX_BYTES) -> bytes:
    """
    Read an uploaded file in chunks, enforcing a hard byte ceiling.
    Resets the file pointer to 0 before reading.
    """
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadValidationError(
                f'File exceeds the {max_bytes // (1024 * 1024)} MB size limit.'
            )
        chunks.append(chunk)

    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    return b''.join(chunks)


def validate_upload(
    file_obj,
    *,
    allowed_extensions: frozenset[str],
    max_bytes: int = DEFAULT_MAX_BYTES,
    require_magic: bool = True,
) -> tuple[bytes, str]:
    """
    Validate and read an uploaded file.

    Returns (file_bytes, extension).
    Raises UploadValidationError on any failure.
    """
    name = getattr(file_obj, 'name', '') or 'upload'
    ext = _extension(name)

    if ext not in allowed_extensions:
        allowed = ', '.join(sorted(allowed_extensions))
        raise UploadValidationError(
            f"File '{name}' has an invalid extension. Allowed: {allowed}."
        )

    # Reject empty uploads and enforce declared size before full read
    declared = getattr(file_obj, 'size', None)
    if declared is not None and declared > max_bytes:
        raise UploadValidationError(
            f"File '{name}' exceeds the {max_bytes // (1024 * 1024)} MB size limit."
        )

    data = read_limited(file_obj, max_bytes)

    if not data:
        raise UploadValidationError(f"File '{name}' is empty.")

    if require_magic and not _matches_magic(data[:16], ext):
        raise UploadValidationError(
            f"File '{name}' content does not match its declared type ({ext})."
        )

    return data, ext
