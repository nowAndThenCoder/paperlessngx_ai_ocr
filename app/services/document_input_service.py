# app/services/document_input_service.py
import io
from typing import List, Tuple

import pymupdf as fitz  # PyMuPDF
from PIL import Image

from app.domain.models.job import FileType, PageInputData


class DocumentInputService:
    """
    Handles the slicing of various document formats into individual page images.
    To minimize RAM, it returns a list of bytes rather than B64 strings.
    """

    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    def parse_pdf(self, file_bytes: bytes) -> List[PageInputData]:
        """Slices a PDF/PDF-A into individual PNG images. Returns (page_num, bytes, width, height)."""
        pages = []

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        # Calculate scale factor to achieve the desired DPI (PyMuPDF default is 72 DPI)
        dpi_scale = self.dpi / 72
        matrix = fitz.Matrix(dpi_scale, dpi_scale)

        for page_num in range(len(doc)):
            page_obj = doc.load_page(page_num)
            pix = page_obj.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")

            page = PageInputData(
                page_number=page_num + 1,
                page_width=float(pix.width),
                page_height=float(pix.height)
            )
            page.page_bytes = img_bytes

            pages.append(page)

        doc.close()
        return pages

    def parse_image(self, file_bytes: bytes) -> List[PageInputData]:
        """Handles single-page image formats (JPG, PNG, BMP, GIF, etc.). Returns (page_num, bytes, width, height)."""
        try:
            img = Image.open(io.BytesIO(file_bytes))
            width, height = img.size

            pages = []

            page = PageInputData(
                page_number=1,
                page_width=float(width),
                page_height=float(height)
            )
            page.page_bytes = file_bytes
            
            pages.append(page)

            return pages
        except Exception:
            return []

    def split_file(self, file_bytes: bytes, file_type: FileType) -> List[PageInputData]:
        """Main entry point to split documents based on their type. Returns (page_num, bytes, width, height)."""
        if file_type == FileType.PDF:
            return self.parse_pdf(file_bytes)

        return self.parse_image(file_bytes)
