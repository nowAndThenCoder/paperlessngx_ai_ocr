# test/test_ocr_parsing_regression.py
import unittest
from uuid import UUID
from app.services.service_provider import service_provider
from app.services.ocr_query_service import OcrQueryService

class TestOcrParsingRegression(unittest.TestCase):
    def test_parse_specific_job_from_redis(self):
        # Job ID aus dem User-Request
        job_id = UUID("52793ceb-fa76-4fda-905d-3f79daffc2d4")
        
        # 1. Job aus Redis laden
        job = service_provider.job_repository.find_by_id(job_id)
        self.assertIsNotNone(job, f"Job {job_id} not found in Redis")
        
        print(f"\nTesting Job: {job_id}")
        
        ocr_service = OcrQueryService()
        
        # Wir prüfen jede Seite des Jobs
        for source_page in job.source_pages:
            print(f"\nProcessing Page {source_page.page_number}...")
            
            raw_result = source_page.intermediate_ocr_unparsed_page_result
            self.assertIsNotNone(raw_result, f"Raw OCR result missing for page {source_page.page_number}")
            
            # Wir simulieren den Parsing-Prozess, wie er im OcrParseResponseCommand passiert.
            # Da wir hier eine einzelne Seite testen, setzen wir den Offset auf 1.
            offset = 1 
            
            parsed_doc = ocr_service.parse_ocr_string_to_document(offset, raw_result)
            
            print(f"Parsed Document: {parsed_doc}")
            
            if parsed_doc and parsed_doc.pages:
                for page in parsed_doc.pages:
                    print(f"  - Found OCR Page ID: {page.page_id}, Lines: {len(page.text_lines)}")
                    for line in page.text_lines:
                        print(f"    [{line.ymin}, {line.xmin}] {line.text}")
            else:
                print("  - Result: Parsed Document is EMPTY or None!")
                self.assertIsNotNone(parsed_doc.pages, f"Parsing failed for page {source_page.page_number}")

if __name__ == "__main__":
    unittest.main()
