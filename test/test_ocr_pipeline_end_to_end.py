# test/test_reprocess_job.py
import unittest
from uuid import UUID
from app.services.service_provider import service_provider
from app.domain.commands import (
    OcrPageCommand, 
    OcrPageTextOnlyCommand, 
    OcrParseResponseCommand
)
from app.domain.models.job import JobStatus

class TestReprocessJob(unittest.TestCase):
    def test_reexecute_ocr_for_specific_job(self):
        # Job ID from request
        job_id = UUID("52793ceb-fa76-4fda-905d-3f79daffc2d4")
        
        # 1. Load Job
        job = service_provider.job_repository.find_by_id(job_id)
        self.assertIsNotNone(job, f"Job {job_id} not found in Redis")
        
        print(f"\nDirectly testing OCR service for Job: {job_id}")
        
        ocr_service = service_provider.ocr_service
        
        # 2. Execute OCR directly on the source pages
        for source_page in job.source_pages:
            page_num = source_page.page_number
            print(f"Extracting Page {page_num}...")
            
            try:
                # Call the service directly bypassing the Command layer
                raw_result = ocr_service.process_page_with_boxes(source_page.page_bytes)
                
                print(f"  - [OK] OCR extraction completed")
                print(f"  - RAW JSON OUTPUT:\n{raw_result}")
                print("-" * 40)
                
                self.assertIsNotNone(raw_result, f"OCR service returned None for page {page_num}")
                self.assertTrue(len(raw_result) > 0, f"OCR service returned empty string for page {page_num}")
                
            except Exception as e:
                print(f"  - [FAILED] Exception during direct OCR call for page {page_num}: {e}")
                self.fail(f"OCR Service failed for page {page_num}: {e}")
        
        # 4. Final save and verification
        service_provider.job_repository.save(job)
        
        # Verify that raw OCR results are now populated
        for page in job.source_pages:
            # Use getattr to avoid Pydantic AttributeError if the field is missing from the loaded object
            raw_result = getattr(page, "intermediate_ocr_page_unparsed_result", None)
            
            self.assertIsNotNone(
                raw_result, 
                f"Raw OCR result missing for page {page.page_number} after reprocessing"
            )
            print(f"Page {page.page_number} RAW JSON:\n{raw_result}")
            print("-" * 40)

if __name__ == "__main__":
    unittest.main()
