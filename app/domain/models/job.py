# ocr_engine/app/domain/models/job.py
import json
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Dict, List, Optional
from uuid import UUID

from app.domain.models.page import PageInputData
from app.services.job_storage_service import job_storage_service


class FileType(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"
    WEBP = "webp"
    UNKNOWN = "unknown"


class JobStatus(IntEnum):
    NOT_STARTED = 0
    OCR_RUNNING = 11
    OCR_PARSING = 12
    OCR_RUNNING_TEXT_ONLY = 13
    PDF_CREATION = 20
    VECTORIZING = 30
    PERSISTING_LANCEDB = 31
    SUCCEEDED = 100
    FAILED = 999

    def to_friendly_string(self) -> str:
        mapping = {
            JobStatus.NOT_STARTED: "notStarted",
            JobStatus.OCR_RUNNING: "running",
            JobStatus.OCR_RUNNING_TEXT_ONLY: "running",
            JobStatus.OCR_PARSING: "running",
            JobStatus.PDF_CREATION: "running",
            JobStatus.VECTORIZING: "succeeded",
            JobStatus.PERSISTING_LANCEDB: "succeeded",
            JobStatus.SUCCEEDED: "succeeded",
            JobStatus.FAILED: "failed",
        }
        return mapping[self]


class JobHistoryEntry:
    def __init__(self, timestamp: str, status: JobStatus, message: str):
        self.timestamp = timestamp
        self.status = status
        self.message = message

    def json(self) -> str:
        return json.dumps({"timestamp": self.timestamp, "status": self.status.value, "message": self.message})

    @classmethod
    def from_dict(cls, data: Dict) -> "JobHistoryEntry":
        return cls(timestamp=data["timestamp"], status=JobStatus(data["status"]), message=data["message"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class Job:
    """
    Domain model for an OCR job.

    Transparent facade over the Redis storage layer (``job_storage_service``):

    - Job meta (status, counters, timestamps, source-page metadata,
      error message) lives under ``job:{id}:meta``.
    - Page blobs live under ``job:{id}:page:{n}``.
    - Page OCR results live under ``job:{id}:result:{n}``.
    - The final searchable PDF lives under ``job:{id}:final_pdf``.

    Byte payloads (blobs, final PDF) are intentionally NOT stored inside
    the JSON meta to keep it small and to avoid binary→JSON overhead.
    """

    def __init__(
        self,
        job_id: UUID,
        model_id: Optional[str] = None,
        file_type: Optional[str] = None,
    ):
        self.job_id: UUID = job_id
        self.model_id: Optional[str] = model_id
        self.file_type: Optional[str] = file_type
        self._created_at: Optional[str] = _now_iso()
        self._updated_at: Optional[str] = _now_iso()
        self._status: JobStatus = JobStatus.NOT_STARTED
        self._total_pages: int = 0
        self._processed_pages: int = 0
        self.source_pages: Optional[List[PageInputData]] = None
        self._final_pdf_bytes: Optional[bytes] = None
        self.error_message: Optional[str] = None

    # ------------------------------------------------------------------
    # Properties mit echtem Mehrwert
    # ------------------------------------------------------------------
    @property
    def status(self) -> JobStatus:
        return self._status

    @status.setter
    def status(self, value: JobStatus) -> None:
        self._status = value
        self._updated_at = _now_iso()

    @property
    def created_at(self) -> Optional[str]:
        return self._created_at

    @property
    def updated_at(self) -> Optional[str]:
        return self._updated_at

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @total_pages.setter
    def total_pages(self, value: int) -> None:
        self._total_pages = max(0, int(value))

    @property
    def processed_pages(self) -> int:
        return self._processed_pages

    @processed_pages.setter
    def processed_pages(self, value: int) -> None:
        self._processed_pages = max(0, int(value))

    @property
    def final_pdf_bytes(self) -> Optional[bytes]:
        if self._final_pdf_bytes is not None:
            return self._final_pdf_bytes
        data = job_storage_service.get_final_pdf(self.job_id)
        if data is not None:
            self._final_pdf_bytes = data
        return self._final_pdf_bytes

    @final_pdf_bytes.setter
    def final_pdf_bytes(self, value: Optional[bytes]) -> None:
        self._final_pdf_bytes = value

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def get_completion_percentage(self) -> float:
        """Returns 0..100 representing the OCR progress of this job."""
        if self._total_pages <= 0:
            return 0.0
        pct = (self._processed_pages / self._total_pages) * 100.0
        return min(100.0, max(0.0, pct))

    def touch(self) -> None:
        """Bumps ``updated_at`` without modifying any other state."""
        self._updated_at = _now_iso()

    def mark_page_processed(self) -> None:
        """
        Increments ``processed_pages`` (capped at ``total_pages``) and
        touches ``updated_at``.
        """
        self._processed_pages = min(self._total_pages, self._processed_pages + 1)
        self.touch()

    # ------------------------------------------------------------------
    # Serialization (JSON <-> Job)
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """
        Serializes the *meta* of the job.

        Page blobs (``job:{id}:page:{n}``) and the final PDF
        (``job:{id}:final_pdf``) are intentionally excluded – they live
        under separate Redis keys to keep this meta-document small and
        to avoid binary→JSON encoding overhead.
        """
        return {
            "job_id": str(self.job_id),
            "model_id": self.model_id,
            "file_type": self.file_type,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "status": int(self._status),
            "total_pages": self._total_pages,
            "processed_pages": self._processed_pages,
            "error_message": self.error_message,
            "source_pages": [p.model_dump() for p in self.source_pages] if self.source_pages else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Job":
        """Restores a ``Job`` instance from its serialized meta dict."""
        job_id = UUID(str(data["job_id"]))
        job = cls(job_id=job_id, model_id=data.get("model_id"), file_type=data.get("file_type"))

        job._created_at = data.get("created_at") or job._created_at
        job._updated_at = data.get("updated_at") or job._updated_at
        job._status = JobStatus(int(data.get("status", JobStatus.NOT_STARTED.value)))
        job._total_pages = int(data.get("total_pages", 0))
        job._processed_pages = int(data.get("processed_pages", 0))
        job.error_message = data.get("error_message")

        sp_raw = data.get("source_pages")
        if sp_raw:
            job.source_pages = [PageInputData(**item) for item in sp_raw]

        # Cache the final PDF lazily (don't load it eagerly here)
        job._final_pdf_bytes = None

        return job

    def json(self) -> str:
        """Convenience: serialize to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "Job":
        """Convenience: deserialize from a JSON string."""
        return cls.from_dict(json.loads(raw))
