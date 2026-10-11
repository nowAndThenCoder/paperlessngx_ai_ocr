# app/services/input_handler.py
import io
from typing import List, Tuple

import fitz  # PyMuPDF
from PIL import Image

from app.domain.models.job import FileType


class InputHandler:
    """
    Handles the slicing of various document formats into individual page images.
    To minimize RAM, it returns a list of bytes rather than B64 strings.
    """

    def parse_pdf(self, file_bytes: bytes) -> List[Tuple[int, bytes]]:
        """Slices a PDF/PDF-A into individual PNG images."""
        pages = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            pages.append((page_num + 1, img_bytes))

        doc.close()
        return pages

    def parse_image(self, file_bytes: bytes) -> List[Tuple[int, bytes]]:
        """Handles single-page image formats (JPG, PNG, BMP, GIF, etc.)."""
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()
            return [(1, file_bytes)]
        except Exception:
            return []

    def split_file(self, file_bytes: bytes, file_type: FileType) -> List[Tuple[int, bytes]]:
        """Main entry point to split documents based on their type."""
        if file_type == FileType.PDF:
            return self.parse_pdf(file_bytes)

        return self.parse_image(file_bytes)
