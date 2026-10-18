# app/services/pdf_service.py
from typing import List
from uuid import UUID

import pymupdf as fitz  # PyMuPDF

from app.domain.models.job import Job
from app.domain.models.ocr import OcrDocument
from app.domain.models.page import PageInputData


class PdfService:
    """
    Service for generating searchable PDFs from OCR results.
    Transforms normalized OCR coordinates (0-1000) into PDF points.
    """

    def generate_searchable_pdf(self, job: Job) -> bytes:
        """
        Generates a searchable PDF for the entire job.

        Args:
            job: The Job object containing source pages and OCR results.

        Returns:
            The raw bytes of the generated searchable PDF.
        """
        doc = fitz.open()

        if not job.source_pages:
            raise ValueError("No source pages metadata found in Job. Cannot generate PDF.")

        for physical_page in job.source_pages:
            # We create the page directly in the main document
            self._add_pdf_page(doc, physical_page)

        # Save to bytes
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def _add_pdf_page(self, doc: fitz.Document, physical_page: PageInputData):
        """
        Adds a single page to the document containing the original image
        as background and a searchable invisible text layer.
        """
        # Get image bytes
        img_bytes = physical_page.page_bytes
        if not img_bytes:
            # Create a blank page if no image is available
            doc.new_page(width=physical_page.page_width, height=physical_page.page_height)
            return

        # Use image dimensions for the page
        img = fitz.Pixmap(img_bytes)
        page = doc.new_page(width=img.width, height=img.height)

        # Insert the image to cover the whole page
        page.insert_image(page.rect, stream=img_bytes)

        # If we have OCR results, add the invisible text layer
        ocr_results = physical_page.intermediate_ocr_page_result
        if ocr_results and ocr_results.pages:
            # We only care about the first logical page of the result for this physical page
            ocr_page = ocr_results.pages[0]
            
            if ocr_page.text_lines:
                for line in ocr_page.text_lines:
                    if not line.text:
                        continue

                    # Transform normalized coordinates (0-1000) to PDF points
                    x0 = (line.xmin / 1000.0) * img.width
                    y0 = (line.ymin / 1000.0) * img.height
                    x1 = (line.xmax / 1000.0) * img.width
                    y1 = (line.ymax / 1000.0) * img.height

                    # Define the rectangle for the text box
                    rect = fitz.Rect(x0, y0, x1, y1)

                    # Use insert_textbox for precise placement and scaling
                    page.insert_textbox(
                        rect,
                        line.text,
                        fontsize=10, 
                        render_mode=3,
                        align=0 # Left align
                    )


# Singleton instance
pdf_service = PdfService()
