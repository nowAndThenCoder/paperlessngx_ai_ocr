from __future__ import annotations
# ocr_engine/app/domain/commands.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.job import Job, JobStatus
from app.domain.models.ocr import OcrDocument
from app.services.service_provider import service_provider
from app.services.config import logging

logger = logging.getLogger(__name__)


class BaseCommand(BaseModel, ABC):
    job_id: UUID

    def load_job(self) -> Job:
        job = service_provider.job_repository.find_by_id(self.job_id)
        if not job:
            raise ValueError(f"Job {self.job_id} not found in repository.")
        return job

    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def create_next_command(self) -> Optional[BaseCommand]:
        pass


class OcrDocumentCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Orchestrates the OCR pipeline by checking for unprocessed pages.
        """
        job = self.load_job()

        # chain will be called: OcrDocumentCommand -> OcrPageCommand -> OcrPageTextOnlyCommand -> OcrParseResponseCommand -> OcrDocumentCommand
        for single_source_page in job.source_pages:
            if single_source_page.intermediate_ocr_page_result is None:
                return True

        # chain will be called: OcrDocumentCommand -> CreateSearchablePdfCommand -> OcrDocumentCommand
        if job.final_pdf_bytes is None:
            return True

        # chain will be called: OcrDocumentCommand -> VectorizeCommand -> PersistLanceDbCommand -> OcrDocumentSucceededCommand
        for single_source_page in job.source_pages:
            if single_source_page.intermediate_embeddings_result is None:
                return True

        # nothing to do here anymore
        return False

    def create_next_command(self) -> Optional[BaseCommand]:
        """Determines the next step in the pipeline."""

        job = self.load_job()

        for single_source_page in job.source_pages:
            if single_source_page.intermediate_ocr_page_result is None:
                return OcrPageCommand(job_id=self.job_id, page_number=single_source_page.page_number)
        
        if job.final_pdf_bytes is None:
            return CreateSearchablePdfCommand(job_id=self.job_id)
        
        for single_source_page in job.source_pages:
            if single_source_page.intermediate_embeddings_result is None:
                return VectorizeCommand(job_id=self.job_id)           
        
        return None


class OcrPageCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Performs OCR on a single physical page with bounding boxes."""
        
        job = self.load_job()
        job.status = JobStatus.OCR_RUNNING

        found_single_source_page = None
        for single_source_page in job.source_pages:
            if single_source_page.page_number == self.page_number:
                found_single_source_page = single_source_page

        found_single_source_page.intermediate_ocr_page_unparsed_result = service_provider.ocr_service.process_page_with_boxes(found_single_source_page.page_bytes)
        service_provider.job_repository.save(job)

        return True

    def create_next_command(self) -> Optional[BaseCommand]:
        """Transitions to text-only OCR for the same page."""
        return OcrPageTextOnlyCommand(job_id=self.job_id, page_number=self.page_number)


class OcrPageTextOnlyCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Performs text-only OCR on a single physical page."""
        job = self.load_job()
        job.status = JobStatus.OCR_RUNNING_TEXT_ONLY

        found_single_source_page = None
        for single_source_page in job.source_pages:
            if single_source_page.page_number == self.page_number:
                found_single_source_page = single_source_page

        found_single_source_page.intermediate_text_result = service_provider.ocr_service.process_page_without_boxes(found_single_source_page.page_bytes)
        service_provider.job_repository.save(job)

        return True

    def create_next_command(self) -> Optional[BaseCommand]:
        """Transitions to the parsing phase for the same page."""
        return OcrParseResponseCommand(job_id=self.job_id, page_number=self.page_number)


class OcrParseResponseCommand(BaseCommand):
    page_number: int

    def execute(self) -> bool:
        """Processes raw OCR outputs for a single page into structured OcrDocuments."""
        job = self.load_job()
        job.status = JobStatus.OCR_PARSING

        total_page_count = 0
        found_single_source_page = None
        
        for single_source_page in job.source_pages:
            if single_source_page.intermediate_ocr_page_result and single_source_page.intermediate_ocr_page_result.pages:
                count_pages = len(single_source_page.intermediate_ocr_page_result.pages)
                total_page_count += count_pages
            if single_source_page.page_number == self.page_number:
                found_single_source_page = single_source_page

        found_single_source_page.intermediate_ocr_page_result = service_provider.ocr_service.parse_ocr_string_to_document(total_page_count + 1, found_single_source_page.intermediate_ocr_page_unparsed_result)
        service_provider.job_repository.save(job)
        
        return True

    def create_next_command(self) -> Optional[BaseCommand]:
        """Transitions back to OcrDocumentCommand to check for the next page."""
        return OcrDocumentCommand(job_id=self.job_id)


class CreateSearchablePdfCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Generates a searchable PDF for the entire document using aggregated OCR results.
        """
        job = self.load_job()
        job.status = JobStatus.PDF_CREATION
        
        pdf_bytes = service_provider.pdf_service.generate_searchable_pdf(job)
        job.final_pdf_bytes = pdf_bytes

        service_provider.job_repository.save(job)
        
        # Export PDF to local file for debugging/verification
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"./test/output/{self.job_id}_{timestamp}.pdf"
        with open(filename, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"PDF exported to local file: {filename}")

        return True


    def create_next_command(self) -> Optional[BaseCommand]:
        """
        Transitions to the vectorization phase.
        """
        return OcrDocumentCommand(job_id=self.job_id)


class VectorizeCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Generates vector embeddings for all pages of the document based on the recognized text only
        """
        job = self.load_job()
        job.status = JobStatus.VECTORIZING

        for source_page in job.source_pages:
            source_page.intermediate_embeddings_result = service_provider.vector_service.vectorize_text(source_page.intermediate_text_result)

        service_provider.job_repository.save(job)

        return True


    def create_next_command(self) -> Optional[BaseCommand]:
        """Transitions to the final persistence phase."""
        return PersistLanceDbCommand(job_id=self.job_id)


class PersistLanceDbCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Moves extracted text and embeddings from Redis to permanent storage in LanceDB.
        """
        job = self.load_job()
        job.status = JobStatus.PERSISTING_LANCEDB
        lancedb_service = service_provider.lancedb_service
        for source_page in job.source_pages:
            lancedb_service.persist_page(
                job_id=self.job_id,
                page_id=source_page.page_number,
                text=source_page.intermediate_text_result,
                embeddings=source_page.intermediate_embeddings_result,
                metadata={"model_id": job.model_id},
            )
        return True

    def create_next_command(self) -> Optional[BaseCommand]:
        """
        Transitions to the success finalization.
        """
        return OcrDocumentSucceededCommand(job_id=self.job_id)


class OcrDocumentSucceededCommand(BaseCommand):
    def execute(self) -> bool:
        """
        Finalizes the job as successfully completed.

        Update JobStatus to SUCCEEDED.
        """
        job = self.load_job()
        job.status = JobStatus.SUCCEEDED
        service_provider.job_repository.save(job)        

        return True

    def create_next_command(self) -> Optional[BaseCommand]:
        return None


class OcrDocumentFailedCommand(BaseCommand):
    error_message: str

    def execute(self) -> bool:
        """
        Finalizes the job as failed.

        Logic: Update JobStatus to FAILED in Redis.
        """
        job = self.load_job()
        job.status = JobStatus.FAILED
        service_provider.job_repository.save(job)
        return True

    def create_next_command(self) -> Optional[BaseCommand]:
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
