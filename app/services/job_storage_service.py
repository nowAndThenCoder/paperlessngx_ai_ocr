# app/services/job_storage_service.py
import json
from typing import Any, Dict, Optional, cast
from uuid import UUID

from app.services.config import logging
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class JobStorageService:
    """
    Low-level service for managing OCR job data in Redis.
    Avoids complex entities and focuses on raw key-value operations
    to maintain a minimal RAM footprint and high resilience.
    """

    def __init__(self):
        self.client = redis_client.get_connection()

    # --- Key Generators ---
    def _meta_key(self, job_id: UUID) -> str:
        return f"job:{job_id}:meta"

    def _page_blob_key(self, job_id: UUID, page_num: int) -> str:
        return f"job:{job_id}:page:{page_num}"

    def _page_result_key(self, job_id: UUID, page_num: int) -> str:
        return f"job:{job_id}:result:{page_num}"

    def _page_text_key(self, job_id: UUID, page_num: int) -> str:
        return f"job:{job_id}:text:{page_num}"

    def _final_pdf_key(self, job_id: UUID) -> str:
        return f"job:{job_id}:final_pdf"

    # --- Job Metadata ---
    def save_job_meta(self, job_id: UUID, metadata: Dict[str, Any]) -> None:
        """Saves job metadata as a JSON string."""
        self.client.set(self._meta_key(job_id), json.dumps(metadata))

    def get_job_meta(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieves job metadata."""
        data = self.client.get(self._meta_key(job_id))
        return json.loads(data) if data else None

    def get_status(self, job_id: UUID) -> Optional[int]:
        """Returns the status of the last history entry."""
        meta = self.get_job_meta(job_id)
        if not meta:
            return None
        return meta.get("status")

    def reset_status(self, job_id: UUID, previous_status: int) -> None:
        """
        Resets the status to a previous value. 
        Adds a history entry to mark the rollback.
        """
        self.add_job_history_entry(job_id, previous_status, "Status reset after failure")

    def add_job_history_entry(self, job_id: UUID, status: Any, message: str = "") -> None:
        """
        Adds a status entry to the job history and updates the current status.
        Ensures the record is created if it doesn't exist.
        """
        meta = self.get_job_meta(job_id)
        if meta is None:
            meta = {"job_id": str(job_id), "history": []}
        
        if "history" not in meta or not isinstance(meta["history"], list):
            meta["history"] = []

        entry = {
            "timestamp": self.get_now_iso(),
            "status": status if isinstance(status, int) else status.value,
            "message": message
        }
        
        meta["history"].append(entry)
        meta["status"] = entry["status"]
        meta["updated_at"] = entry["timestamp"]
        
        self.save_job_meta(job_id, meta)

    # --- Page Blobs (Input Images) ---
    def save_page_image(self, job_id: UUID, page_number: int, image_bytes: bytes) -> None:
        """Saves a raw image blob for a specific page."""
        self.client.set(self._page_blob_key(job_id, page_number), image_bytes)

    def get_page_image(self, job_id: UUID, page_number: int) -> Optional[bytes]:
        """Retrieves a raw image blob for a specific page."""
        data = cast(bytes | None, self.client.get(self._page_blob_key(job_id, page_number)))
        return data if data else None

    # --- Page Results (OCR Output) ---
    def save_page_ocr_result(self, job_id: UUID, page_number: int, result: Any) -> None:
        """Saves the OCR result for a specific page."""
        # Result can be a dict or list, store as JSON
        self.client.set(self._page_result_key(job_id, page_number), json.dumps(result))

    def get_page_ocr_result(self, job_id: UUID, page_number: int) -> Optional[Any]:
        """Retrieves the OCR result for a specific page."""
        data = self.client.get(self._page_result_key(job_id, page_number))
        return json.loads(data) if data else None

    def save_page_text(self, job_id: UUID, page_number: int, text: str) -> None:
        """Saves the text-only OCR result for a specific page."""
        self.client.set(self._page_text_key(job_id, page_number), text)

    def get_page_text(self, job_id: UUID, page_number: int) -> Optional[str]:
        """Retrieves the text-only OCR result for a specific page."""
        return self.client.get(self._page_text_key(job_id, page_number))

    def save_page_embeddings(self, job_id: UUID, page_number: int, embeddings: list[float]) -> None:
        """Saves vector embeddings for a specific page."""
        # Store as JSON string
        self.client.set(f"job:{job_id}:embeddings:{page_number}", json.dumps(embeddings))

    def get_page_embeddings(self, job_id: UUID, page_number: int) -> Optional[list[float]]:
        """Retrieves vector embeddings for a specific page."""
        data = self.client.get(f"job:{job_id}:embeddings:{page_number}")
        return json.loads(data) if data else None

    def get_now_iso(self) -> str:
        """Returns current UTC time in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # --- Final Output ---
    def save_final_pdf(self, job_id: UUID, pdf_bytes: bytes) -> None:
        """Saves the final searchable PDF."""
        self.client.set(self._final_pdf_key(job_id), pdf_bytes)

    def get_final_pdf(self, job_id: UUID) -> Optional[bytes]:
        """Retrieves the final searchable PDF."""
        data = cast(bytes | None, self.client.get(self._final_pdf_key(job_id)))
        return data if data else None


# Singleton instance for use across the app
job_storage_service = JobStorageService()
