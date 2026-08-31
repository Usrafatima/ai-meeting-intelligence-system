"""
Module 6 - Dashboard & Meeting Details
Serving meeting recordings so the player can seek.

The brief asks that clicking a timestamp jump to that point in the recording.
That is not a front-end trick: a browser will only seek an <audio>/<video>
element whose source honours HTTP range requests. The player asks for a byte
window, the server answers 206 Partial Content, and playback starts there
without downloading everything before it.

A plain file response cannot do this -- the element loads start to finish and the
scrub bar stays inert. Hence this module.

Reference: RFC 9110 sections 14.1-14.4 (Range, Content-Range, 206, 416).
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Iterator, Optional, Tuple

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

# Read size per chunk. Large enough to keep syscalls down, small enough that a
# seek to the middle of a long recording does not buffer needlessly.
CHUNK_SIZE = 512 * 1024

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeNotSatisfiable(Exception):
    """The requested range falls outside the file. Answered with 416."""

    def __init__(self, file_size: int):
        self.file_size = file_size
        super().__init__(f"Requested range not satisfiable for a {file_size} byte file")


def guess_content_type(filename: str, stored_type: Optional[str] = None) -> str:
    """
    Best content type for a recording.

    Prefers what was recorded at upload, falling back to the extension. The
    generic default is deliberately octet-stream: a wrong media type stops some
    browsers playing the file at all, so an honest unknown is safer than a guess.
    """
    if stored_type and stored_type != "application/octet-stream":
        return stored_type

    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """
    Resolve a Range header into inclusive start and end byte offsets.

    Handles the three forms that matter for media playback:

        bytes=0-        from an offset to the end   (what a player sends on seek)
        bytes=500-999   an explicit window
        bytes=-500      the trailing N bytes

    Raises RangeNotSatisfiable when the range cannot be met. Malformed headers
    are not an error: RFC 9110 says an unparseable Range must be ignored, so the
    caller falls back to serving the whole file.
    """
    match = _RANGE_RE.match((range_header or "").strip())
    if not match:
        raise ValueError("Unparseable Range header")

    raw_start, raw_end = match.groups()

    if not raw_start and not raw_end:
        raise ValueError("Range specifies neither a start nor an end")

    if not raw_start:
        # Suffix form: the last N bytes.
        suffix = int(raw_end)
        if suffix <= 0:
            raise RangeNotSatisfiable(file_size)
        start = max(0, file_size - suffix)
        end = file_size - 1
    else:
        start = int(raw_start)
        end = int(raw_end) if raw_end else file_size - 1

    if start >= file_size or start > end:
        raise RangeNotSatisfiable(file_size)

    # A player may optimistically ask past the end; clamp rather than reject.
    end = min(end, file_size - 1)
    return start, end


def _iter_file(path: Path, start: int, length: int) -> Iterator[bytes]:
    """Yield `length` bytes from `path` beginning at `start`, in chunks."""
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def resolve_local_path(base_dir: str, storage_path: str) -> Path:
    """
    Turn a stored relative path into an absolute one, refusing to escape the
    upload directory.

    The value comes from our own database, but a traversal check costs nothing
    and means a corrupted or tampered row cannot be used to read arbitrary files
    off the server.
    """
    base = Path(base_dir).resolve()
    candidate = Path(storage_path)

    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()

    if resolved != base and base not in resolved.parents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found"
        )

    return resolved


def build_range_response(
    path: Path,
    *,
    filename: str,
    content_type: str,
    range_header: Optional[str] = None,
) -> StreamingResponse:
    """
    Stream a file, honouring a Range header when one is present.

    Returns 206 with Content-Range for a range request, and 200 for a plain one.
    Both carry `Accept-Ranges: bytes`, which is how the browser learns it is
    allowed to seek at all.
    """
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording is missing from storage",
        )

    file_size = path.stat().st_size

    headers = {
        "Accept-Ranges": "bytes",
        # inline: play in place rather than prompting a download.
        "Content-Disposition": f'inline; filename="{Path(filename).name}"',
        "Cache-Control": "private, max-age=3600",
    }

    if not range_header:
        headers["Content-Length"] = str(file_size)
        return StreamingResponse(
            _iter_file(path, 0, file_size),
            status_code=status.HTTP_200_OK,
            media_type=content_type,
            headers=headers,
        )

    try:
        start, end = parse_range_header(range_header, file_size)
    except RangeNotSatisfiable:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    except ValueError:
        # Unparseable range: ignore it and serve the whole file, per RFC 9110.
        headers["Content-Length"] = str(file_size)
        return StreamingResponse(
            _iter_file(path, 0, file_size),
            status_code=status.HTTP_200_OK,
            media_type=content_type,
            headers=headers,
        )

    length = end - start + 1
    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    headers["Content-Length"] = str(length)

    return StreamingResponse(
        _iter_file(path, start, length),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=content_type,
        headers=headers,
    )
