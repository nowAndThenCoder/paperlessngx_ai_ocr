# ocr_engine/app/domain/models/job.py
from __future__ import annotations

from enum import Enum, IntEnum
from typing import  List, Optional
from uuid import UUID

from app.domain.models.page import PageInputData


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
    OCR_RUNNING = 1
    OCR_RUNNING_TEXT_ONLY = 2
    OCR_PARSING = 3
    PDF_CREATION = 4
    VECTORIZING = 5
    PERSISTING_LANCEDB = 6
    SUCCEEDED = 10
    FAILED = -1

    def to_friendly_string(self) -> str:
        mapping = {
            JobStatus.NOT_STARTED: "running",
            JobStatus.OCR_RUNNING: "running",
            JobStatus.OCR_RUNNING_TEXT_ONLY: "running",
            JobStatus.OCR_PARSING: "running",
            JobStatus.PDF_CREATION: "running",
            JobStatus.VECTORIZING: "running",
            JobStatus.PERSISTING_LANCEDB: "running",
            JobStatus.SUCCEEDED: "succeeded",
            JobStatus.FAILED: "failed",
        }
        return mapping[self]


class Job:
    """
    Domain model for an OCR job.
    """

    def __init__(
        self,
        job_id: UUID,
        model_id: Optional[str] = None,
        file_type: Optional[str] = None,
    ):
        self.job_id: UUID = job_id
        self.model_id: Optional[str] = model_id
        self.file_type: str = file_type

        self.source_pages: Optional[List[PageInputData]] = None
        self.status: JobStatus = JobStatus.NOT_STARTED
        self.final_pdf_bytes: Optional[bytes] = None

    def get_full_text(self) -> str:
        """
        Concatenates the intermediate_text_result from all source pages,
        separated by the DOCUMENT_PAGE_BREAK string.
        """
        if not self.source_pages:
            return ""
        
        texts = [
            page.intermediate_text_result 
            for page in self.source_pages 
            if page.intermediate_text_result is not None
        ]
        
        return "=== DOCUMENT_PAGE_BREAK ===".join(texts)
