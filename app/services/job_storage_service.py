# app/services/job_storage_service.py
import json
from typing import Any, Dict, Optional, cast
from uuid import UUID

from app.services.redis_client import redis_client


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

    def update_job_meta(self, job_id: UUID, updates: Dict[str, Any]) -> None:
        """Updates specific fields in the job metadata."""
        meta = self.get_job_meta(job_id) or {}
        meta.update(updates)
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
