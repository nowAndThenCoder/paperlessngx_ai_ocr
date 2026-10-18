
import os
from uuid import UUID
from app.repositories.job_repository import job_repository
from app.services.pdf_service import pdf_service

def test_generate_pdf_from_existing_redis_job():
    # The specific job ID provided by the user
    job_id_str = "1b265a3d-0da8-4c77-be25-fb62166ecb2f"
    job_id = UUID(job_id_str)

    print(f"Loading job {job_id} from Redis...")
    job = job_repository.find_by_id(job_id)

    if job is None:
        raise AssertionError(f"Job {job_id} not found in Redis. Please ensure the job exists before running this test.")

    print(f"Job found. Status: {job.status}. Generating PDF...")
    
    try:
        pdf_bytes = pdf_service.generate_searchable_pdf(job)
        
        if not pdf_bytes:
            raise AssertionError("Generated PDF bytes are empty.")

        # Save the result to a file for manual verification
        output_filename = f"./test/output/test_output_{job_id_str}.pdf"
        with open(output_filename, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"Successfully generated PDF and saved to {output_filename}")
        
    except Exception as e:
        print(f"Failed to generate PDF for job {job_id}: {e}")
        raise e

if __name__ == "__main__":
    # This allows running the test as a standalone script
    try:
        test_generate_pdf_from_existing_redis_job()
        print("Test PASSED")
    except Exception as e:
        print(f"Test FAILED: {e}")
        exit(1)
