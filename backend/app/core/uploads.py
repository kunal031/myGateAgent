"""Where an uploaded file waits between the request and the job.

A PDF arrives on one request and is parsed by a job that may run
elsewhere. Locally "elsewhere" is another thread sharing a filesystem, so
a temp file is enough. On Lambda it is a different container with its own
`/tmp`, and the bytes cannot ride along in the invoke payload either --
asynchronous invokes cap at 256 KB, which a question paper exceeds
immediately.

So an uploaded file goes to object storage when a bucket is configured
and to a temp directory otherwise, behind one pair of functions. The
caller never branches on which.

Files are deleted once parsed: a question paper becomes rows, and keeping
the original would grow storage for no benefit.
"""

import logging
import os
import tempfile
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


def _bucket() -> str:
    return (settings.UPLOAD_BUCKET or "").strip()


def stage_upload(paper_id: int, raw: bytes) -> str:
    """Put the bytes where the job will find them. Returns a locator."""
    name = f"uploads/paper-{paper_id}.pdf"

    if _bucket():
        import boto3

        boto3.client("s3").put_object(
            Bucket=_bucket(), Key=name, Body=raw,
            ContentType="application/pdf",
        )
        logger.info("Staged upload to s3://%s/%s", _bucket(), name)
        return f"s3://{_bucket()}/{name}"

    path = Path(tempfile.gettempdir()) / f"paper-{paper_id}.pdf"
    path.write_bytes(raw)
    return str(path)


def fetch_upload(locator: str, paper_id: int) -> Path:
    """Get the file onto local disk, since extractors work on paths."""
    if not locator.startswith("s3://"):
        return Path(locator)

    import boto3

    bucket, _, key = locator[len("s3://"):].partition("/")
    local = Path(tempfile.gettempdir()) / f"paper-{paper_id}.pdf"
    boto3.client("s3").download_file(bucket, key, str(local))
    return local


def discard_upload(locator: str) -> None:
    """Remove the staged file. Never raises: the parse already succeeded,
    and failing the job over cleanup would re-run work for nothing."""
    try:
        if locator.startswith("s3://"):
            import boto3

            bucket, _, key = locator[len("s3://"):].partition("/")
            boto3.client("s3").delete_object(Bucket=bucket, Key=key)
        else:
            Path(locator).unlink(missing_ok=True)
    except Exception:
        logger.warning("Could not discard staged upload %s", locator,
                       exc_info=True)
