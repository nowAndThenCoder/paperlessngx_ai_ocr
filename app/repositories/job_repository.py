# app/repositories/job_repository.py
import json
import base64
from typing import Dict, Optional, List, Any
from uuid import UUID

from app.domain.models.job import Job, JobStatus
from app.domain.models.page import PageInputData
from app.services.redis_client import redis_client


class JobRepository:
    """
    Repository for Job domain model.
    Decouples the Job entity from the infrastructure (Redis).
    """

    def save(self, job: Job) -> None:
        """Persists the current job state back into Redis as JSON."""
        client = redis_client.get_connection()
        
        job_dict = {
            "job_id": str(job.job_id),
            "model_id": job.model_id,
            "file_type": job.file_type,
            "status": int(job.status),
            "final_pdf_bytes": base64.b64encode(job.final_pdf_bytes).decode('utf-8') if job.final_pdf_bytes else None,
            "source_pages": [
                {**p.model_dump(), "page_bytes": base64.b64encode(p.page_bytes).decode('utf-8') if p.page_bytes else None}
                for p in job.source_pages
            ] if job.source_pages else None
        }
        
        client.set(f"job:{job.job_id}", json.dumps(job_dict))

    def create_job(self, file_type: str, source_pages_data: Optional[List[PageInputData]] = None) -> Job:
        """
        Creates a new Job entity, initializes its state and persists it.
        """
        import uuid
        job_id = uuid.uuid4()
        job = Job(job_id=job_id, file_type=file_type)
        job.source_pages = source_pages_data
            
        self.save(job)
        return job

    def find_by_id(self, job_id: UUID) -> Optional[Job]:
        """
        Retrieves a Job instance by its ID from Redis JSON.
        Returns None if the job is not found.
        """
        client = redis_client.get_connection()
        data_str = client.get(f"job:{job_id}")
        if not data_str:
            return None
            
        data = json.loads(data_str)
        
        job = Job(
            job_id=UUID(data["job_id"]),
            model_id=data.get("model_id"),
            file_type=data.get("file_type")
        )
        job.status = JobStatus(data["status"])
        job.final_pdf_bytes = base64.b64decode(data["final_pdf_bytes"]) if data.get("final_pdf_bytes") else None
        
        if data.get("source_pages"):
            job.source_pages = [
                PageInputData(
                    **{**p, "page_bytes": base64.b64decode(p["page_bytes"]) if p.get("page_bytes") else None}
                ) for p in data["source_pages"]
            ]
            
        return job

# Singleton instance for use across the app
job_repository = JobRepository()
