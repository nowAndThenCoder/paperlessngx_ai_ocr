# app/repositories/job_repository.py
from typing import Optional
from uuid import UUID

from app.domain.models.job import Job
from app.services.job_storage_service import job_storage_service


class JobRepository:
    """
    Repository for Job domain model.
    Decouples the Job entity from the infrastructure (Redis).
    """

    def save(self, job: Job) -> None:
        """Persists the current job state back into Redis."""
        job_storage_service.save_job_meta(job.job_id, job.to_dict())

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
