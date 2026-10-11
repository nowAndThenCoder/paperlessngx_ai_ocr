# ocr_engine/app/domain/commands.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.job import JobStatus
from app.services.service_provider import service_provider
from app.services.config import logging

logger = logging.getLogger(__name__)


class BaseCommand(BaseModel, ABC):
    job_id: UUID

    def load_job_meta(self) -> Optional[Dict[str, Any]]:
        """
        Loads the current job metadata from Redis.
        Used by all commands to check job state, total pages, etc.
        """
        return service_provider.job_storage.get_job_meta(self.job_id)

    def update_job_meta(self, updates: Dict[str, Any]) -> None:
        """
        Updates job metadata in Redis.
        """
        service_provider.job_storage.update_job_meta(self.job_id, updates)

    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def create_next_command(self) -> Optional["BaseCommand"]:
        pass


class OcrDocumentCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Orchestrates the OCR pipeline by checking for unprocessed pages.
        """
        try:
            job = service_provider.job_repository.find_by_id(self.job_id)
            if not job:
                logger.error(f"Job {self.job_id} not found in repository.")
                return False

            for page_number in range(1, job.total_pages + 1):
                if service_provider.job_storage.get_page_ocr_result(job.job_id, page_number) is None:
                    return True

            return True
        except Exception:
            logger.exception(f"Failed to execute OcrDocumentCommand for job {self.job_id}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """Determines the next step in the pipeline."""
        try:
            job = service_provider.job_repository.find_by_id(self.job_id)
            if not job:
                return None

            for page_number in range(1, job.total_pages + 1):
                if service_provider.job_storage.get_page_ocr_result(job.job_id, page_number) is None:
                    return OcrPageCommand(job_id=self.job_id, page_number=page_number)

            return CreateSearchablePdfCommand(job_id=self.job_id)
        except Exception:
            logger.exception(f"Failed to determine next command for job {self.job_id}")
            return None


class OcrPageCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Performs OCR on a single physical page with bounding boxes."""
        try:
            image_bytes = service_provider.job_storage.get_page_image(self.job_id, self.page_number)
            if not image_bytes:
                logger.error(f"No image bytes found for job {self.job_id} page {self.page_number}")
                return False

            raw_response = service_provider.ocr_service.process_page_with_boxes(image_bytes)
            service_provider.job_storage.save_page_ocr_result(self.job_id, self.page_number, raw_response)

            return True
        except Exception:
            logger.exception(f"Failed to execute OcrPageCommand for job {self.job_id} page {self.page_number}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """Transitions to text-only OCR for the same page."""
        return OcrPageTextOnlyCommand(job_id=self.job_id, page_number=self.page_number)


class OcrPageTextOnlyCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Performs text-only OCR on a single physical page."""
        try:
            image_bytes = service_provider.job_storage.get_page_image(self.job_id, self.page_number)
            if not image_bytes:
                logger.error(f"No image bytes found for job {self.job_id} page {self.page_number}")
                return False

            raw_text = service_provider.ocr_service.process_page_without_boxes(image_bytes)
            service_provider.job_storage.save_page_text(self.job_id, self.page_number, raw_text)

            return True
        except Exception:
            logger.exception(f"Failed to execute OcrPageTextOnlyCommand for job {self.job_id} page {self.page_number}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """Transitions to the parsing phase for the same page."""
        return OcrParseResponseCommand(job_id=self.job_id, page_number=self.page_number)


class OcrParseResponseCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Processes raw OCR outputs for a single page into structured OcrDocuments."""
        try:
            raw_boxes = service_provider.job_storage.get_page_ocr_result(self.job_id, self.page_number)
            raw_text = service_provider.job_storage.get_page_text(self.job_id, self.page_number)

            if raw_boxes is None or raw_text is None:
                logger.error(f"Missing OCR results for job {self.job_id} page {self.page_number}")
                return False

            structured_docs = service_provider.ocr_service.parse_ocr_string_to_document(
                increase_page_ids_by_offset=self.page_number - 1, raw_json_str=raw_boxes
            )

            text_parts = raw_text.split("=== DOCUMENT_BREAK ===")

            if structured_docs.pages:
                for i, page in enumerate(structured_docs.pages):
                    page.raw_text = text_parts[i].strip() if i < len(text_parts) else ""

            service_provider.job_storage.save_page_ocr_result(self.job_id, self.page_number, structured_docs.model_dump())

            return True
        except Exception:
            logger.exception(f"Failed to execute OcrParseResponseCommand for job {self.job_id} page {self.page_number}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """Transitions back to OcrDocumentCommand to check for the next page."""
        return OcrDocumentCommand(job_id=self.job_id)


class CreateSearchablePdfCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Generates a searchable PDF for the entire document using aggregated OCR results.
        """
        try:
            job = service_provider.job_repository.find_by_id(self.job_id)
            if not job:
                logger.error(f"Job {self.job_id} not found for PDF generation")
                return False

            pdf_bytes = service_provider.pdf_service.generate_searchable_pdf(job)
            if not pdf_bytes:
                logger.error(f"PDF generation failed for job {self.job_id}")
                return False

            service_provider.job_storage.save_final_pdf(self.job_id, pdf_bytes)
            return True
        except Exception:
            logger.exception(f"Exception during CreateSearchablePdfCommand for job {self.job_id}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """
        Transitions to the vectorization phase.
        """
        return VectorizeCommand(job_id=self.job_id)


class VectorizeCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Generates vector embeddings for all pages of the document.
        """
        try:
            job = service_provider.job_repository.find_by_id(self.job_id)
            if not job:
                logger.error(f"Job {self.job_id} not found for vectorization")
                return False

            for page_num in range(1, job.total_pages + 1):
                result_data = service_provider.job_storage.get_page_ocr_result(self.job_id, page_num)
                if not result_data:
                    continue

                pages_info = result_data.get("pages", [])
                if not pages_info:
                    continue

                full_page_text = "\n".join([p.get("raw_text", "") for p in pages_info if p.get("raw_text")])

                if not full_page_text:
                    continue

                embeddings = service_provider.vector_service.vectorize_text(full_page_text)
                service_provider.job_storage.save_page_embeddings(self.job_id, page_num, embeddings)

            return True
        except Exception:
            logger.exception(f"Failed to vectorize job {self.job_id}")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """Transitions to the final persistence phase."""
        return PersistLanceDbCommand(job_id=self.job_id)


class PersistLanceDbCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Moves extracted text and embeddings from Redis to permanent storage in LanceDB.
        """
        try:
            job = service_provider.job_repository.find_by_id(self.job_id)
            if not job:
                logger.error(f"Job {self.job_id} not found for persistence")
                return False

            lancedb_service = service_provider.lancedb_service

            for page_num in range(1, job.total_pages + 1):
                result_data = service_provider.job_storage.get_page_result(self.job_id, page_num)
                if not result_data:
                    continue

                pages_info = result_data.get("pages", [])
                full_page_text = "\n".join([p.get("raw_text", "") for p in pages_info if p.get("raw_text")])

                embeddings = service_provider.job_storage.get_page_embeddings(self.job_id, page_num)
                if not embeddings:
                    continue

                lancedb_service.persist_page(
                    job_id=self.job_id,
                    page_id=page_num,
                    text=full_page_text,
                    embeddings=embeddings,
                    metadata={"model_id": job.model_id},
                )

            return True
        except Exception:
            logger.exception(f"Failed to persist job {self.job_id} to LanceDB")
            return False

    def create_next_command(self) -> Optional["BaseCommand"]:
        """
        Transitions to the success finalization.
        """
        return OcrDocumentSucceededCommand(job_id=self.job_id)


class OcrDocumentSucceededCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Finalizes the job as successfully completed.

        Logic:
        1. Update JobStatus to SUCCEEDED in Redis.
        2. Log completion timestamp.
        """
        self.update_job_meta({"status": JobStatus.SUCCEEDED, "completed_at": service_provider.job_storage.get_now_iso()})
        return True

    def create_next_command(self) -> Optional["BaseCommand"]:
        return None


class OcrDocumentFailedCommand(BaseCommand):
    error_message: str

    def execute(self) -> bool:
        """
        Finalizes the job as failed.

        Logic:
        1. Update JobStatus to FAILED in Redis.
        2. Store the error message.
        3. Log completion timestamp.
        """
        self.update_job_meta({"status": JobStatus.FAILED, "error": self.error_message, "completed_at": service_provider.job_storage.get_now_iso()})
        return True

    def create_next_command(self) -> Optional["BaseCommand"]:
        return None


COMMAND_REGISTRY: Dict[str, Type[BaseCommand]] = {
    "OcrDocumentCommand": OcrDocumentCommand,
    "OcrPageCommand": OcrPageCommand,
    "OcrPageTextOnlyCommand": OcrPageTextOnlyCommand,
    "OcrParseResponseCommand": OcrParseResponseCommand,
    "CreateSearchablePdfCommand": CreateSearchablePdfCommand,
    "VectorizeCommand": VectorizeCommand,
    "PersistLanceDbCommand": PersistLanceDbCommand,
    "OcrDocumentSucceededCommand": OcrDocumentSucceededCommand,
    "OcrDocumentFailedCommand": OcrDocumentFailedCommand,
}
