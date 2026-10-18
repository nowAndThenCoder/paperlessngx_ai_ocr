import pymupdf as fitz

from app.domain.models.job import Job
from app.domain.models.page import PageInputData
from .config import logging, settings

logger = logging.getLogger(__name__)

class PdfService:
    """
    Creates searchable PDFs by combining:

    - original image as page background
    - invisible OCR text layer

    OCR coordinates are normalized (0-1000).
    """

    def generate_searchable_pdf(self, job: Job) -> bytes:

        if not job.source_pages:
            raise ValueError("No source pages metadata found in Job. Cannot generate PDF.")

        doc = fitz.open()

        try:
            for physical_page in job.source_pages:
                self._add_pdf_page(doc=doc, physical_page=physical_page)
            return doc.tobytes(garbage=4, clean=True, deflate=True)
        
        finally:
            doc.close()

    def _add_pdf_page(self, doc: fitz.Document, physical_page: PageInputData) -> None:
        img_bytes = physical_page.page_bytes 

        img = fitz.Pixmap(img_bytes)
        
        # Scale pixels back to PDF points based on the configured DPI
        # PDF points are 1/72 inch.
        dpi_scale = settings.OLLAMA_DPI / 72
        page_width = img.width / dpi_scale
        page_height = img.height / dpi_scale

        page = doc.new_page(
            width=page_width,
            height=page_height,
        )

        page.insert_image(
            page.rect,
            stream=img_bytes,
            keep_proportion=False,
            overlay=False,
            width=page_width,
            height=page_height,
        )

        ocr_document = physical_page.intermediate_ocr_page_result

        if not ocr_document or not ocr_document.pages:
            logger.error("no document or pages")
            return

        for ocr_page in ocr_document.pages:
            if not ocr_page.text_lines:
                continue

            for line in ocr_page.text_lines:
                if not line.text or any(v is None for v in [line.xmin, line.ymin, line.xmax, line.ymax]):
                    continue

                x0 = (line.xmin / 1000.0) * page_width
                y0 = (line.ymin / 1000.0) * page_height
                x1 = (line.xmax / 1000.0) * page_width
                y1 = (line.ymax / 1000.0) * page_height

                if x1 <= x0 or y1 <= y0:
                    continue

                rect = fitz.Rect(x0, y0, x1, y1)
                
                # ROTER RAHMEN ZUM DEBUGGEN:
                page.draw_rect(rect, color=(1, 0, 0), width=1)

                # Text sichtbar machen (render_mode=0), um zu sehen, ob er in der Box sitzt
                self._insert_debug_text(page=page, rect=rect, text=line.text)

    def _insert_debug_text(self, page: fitz.Page, rect: fitz.Rect, text: str) -> None:
        font_size = max(min(rect.height, 200), 1)

        for _ in range(50):
            width = fitz.get_text_length(text=text, fontname="helv", fontsize=font_size)            
            if width <= rect.width:
                break

            font_size -= 0.5
            if font_size <= 1:
                font_size = 1
                break

        page.insert_textbox(
            rect,
            text,
            fontsize=font_size,
            fontname="helv",
            color=(0, 0, 1),  # Blauer Text im Debug-Modus, damit man ihn gut vom Schwarz des Bildes unterscheiden kann
            render_mode=0,    # 0 = Sichtbarer Text
            overlay=True,
        )

pdf_service = PdfService()