# app/services/input_handler.py
import io
from typing import List, Tuple

import pymupdf as fitz  # PyMuPDF
from PIL import Image

from app.domain.models.job import FileType


class InputHandler:
    """
    Handles the slicing of various document formats into individual page images.
    To minimize RAM, it returns a list of bytes rather than B64 strings.
    """

    def parse_pdf(self, file_bytes: bytes) -> List[Tuple[int, bytes, int, int]]:
        """Slices a PDF/PDF-A into individual PNG images. Returns (page_num, bytes, width, height)."""
        pages = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            pages.append((page_num + 1, img_bytes, pix.width, pix.height))

        doc.close()
        return pages

    def parse_image(self, file_bytes: bytes) -> List[Tuple[int, bytes, int, int]]:
        """Handles single-page image formats (JPG, PNG, BMP, GIF, etc.). Returns (page_num, bytes, width, height)."""
        try:
            img = Image.open(io.BytesIO(file_bytes))
            width, height = img.size
            return [(1, file_bytes, width, height)]
        except Exception:
            return []

    def split_file(self, file_bytes: bytes, file_type: FileType) -> List[Tuple[int, bytes, int, int]]:
        """Main entry point to split documents based on their type. Returns (page_num, bytes, width, height)."""
        if file_type == FileType.PDF:
            return self.parse_pdf(file_bytes)

        return self.parse_image(file_bytes)
