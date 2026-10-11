# app/services/pdf_service.py
from typing import List
from uuid import UUID

import fitz  # PyMuPDF

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
            return b""

        for physical_page in job.source_pages:
            # We expect each physical page to have its OCR results already populated
            # in the domain model via the pipeline.
            if physical_page.ocr_page_result is None:
                # If OCR results are missing for a page, we still add the image
                # but without a text layer.
                page = self._create_pdf_page(physical_page, None)
                doc.insert_pdf_page(page)
            else:
                page = self._create_pdf_page(physical_page, physical_page.ocr_page_result)
                doc.insert_pdf_page(page)

        # Save to bytes
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def _create_pdf_page(self, physical_page: PageInputData, ocr_results: OcrDocument | None) -> fitz.Document:
        """
        Creates a single-page PDF document containing the original image
        as background and an invisible text layer.

        Args:
            physical_page: The physical page data (image bytes, dimensions).
            ocr_results: The OCR results containing logical pages and lines.

        Returns:
            A fitz.Document containing exactly one page.
        """
        # Create a temporary document for this single page
        page_doc = fitz.open()

        # Get image bytes
        img_bytes = physical_page.page_bytes
        if not img_bytes:
            # Create a blank page if no image is available
            page = page_doc.new_page(width=physical_page.page_width, height=physical_page.page_height)
            return page_doc

        # Create a page with the image as background
        # We create a page based on the image dimensions
        img = fitz.Pixmap(img_bytes)
        page = page_doc.new_page(width=img.width, height=img.height)

        # Insert the image to cover the whole page
        page.insert_image(page.rect, stream=img_bytes)

        # If we have OCR results, add the invisible text layer
        if ocr_results and ocr_results.pages:
            for ocr_page in ocr_results.pages:
                if not ocr_page.text_lines:
                    continue

                for line in ocr_page.text_lines:
                    if not line.text:
                        continue

                    # Transform normalized coordinates (0-1000) to PDF points
                    # PyMuPDF coordinates are (x, y) from top-left.
                    # Line coordinates: ymin, xmin, ymax, xmax

                    x = (line.xmin / 1000.0) * img.width
                    y = (line.ymin / 1000.0) * img.height

                    # We use render_mode=3 to make the text invisible but searchable
                    page.insert_text(
                        fitz.Point(x, y),
                        line.text,
                        fontsize=10,  # Approximation, ideally relative to box height
                        render_mode=3,
                    )

        return page_doc


# Singleton instance
pdf_service = PdfService()
