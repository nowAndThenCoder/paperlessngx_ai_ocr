# app/repositories/job_repository.py
from typing import Optional, List, Any
from uuid import UUID

from app.domain.models.job import Job
from app.domain.models.page import PageInputData
from app.services.job_storage_service import job_storage_service


class JobRepository:
    """
    Repository for Job domain model.
    Decouples the Job entity from the infrastructure (Redis).
    """

    def save(self, job: Job) -> None:
        """Persists the current job state back into Redis."""
        job_storage_service.save_job_meta(job.job_id, job.to_dict())

    def create_job(self, file_type: str, total_pages: int, file_name: str, source_pages_data: List[Any] = None) -> Job:
        """
        Creates a new Job entity, initializes its state and persists it.
        """
        import uuid
        job_id = uuid.uuid4()
        job = Job(job_id=job_id, file_type=file_type)
        job.total_pages = total_pages
        
        if source_pages_data:
            job.source_pages = [
                PageInputData(
                    page_number=d["page_num"], 
                    page_width=d["width"], 
                    page_height=d["height"]
                ) for d in source_pages_data
            ]
            
        self.save(job)
        return job

    def save_page_image(self, job_id: UUID, page_num: int, image_bytes: bytes) -> None:
        """Persists a raw image blob for a specific page."""
        job_storage_service.save_page_image(job_id, page_num, image_bytes)

    def find_by_id(self, job_id: UUID) -> Optional[Job]:
        """
        Retrieves a Job instance by its ID.
        Returns None if the job is not found.
        """
        meta = job_storage_service.get_job_meta(job_id)
        if meta is None:
            return None
        return Job.from_dict(meta)


# Singleton instance for use across the app
job_repository = JobRepository()
