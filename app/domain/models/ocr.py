# app/domain/models/ocr.py
from typing import List, Optional

from pydantic import BaseModel, Field


class OcrLine(BaseModel):
    """
    Represents a single line of text extracted from a document page.
    The coordinates are normalized (0-1000) relative to the image dimensions,
    as provided by the Qwen2.5-VL model.
    """

    text: Optional[str] = None
    ymin: Optional[int] = None  # Top coordinate (0-1000)
    xmin: Optional[int] = None  # Left coordinate (0-1000)
    ymax: Optional[int] = None  # Bottom coordinate (0-1000)
    xmax: Optional[int] = None  # Right coordinate (0-1000)


class OcrPage(BaseModel):
    """
    Represents the OCR result for a single document page.
    """

    page_id: Optional[int] = None
    raw_text: Optional[str] = None  # Pure text extraction (without boxes)
    text_lines: Optional[List[OcrLine]] = None  # Structured lines with bounding boxes


class OcrDocument(BaseModel):
    """
    A collection of OCR pages forming a complete document.
    This class provides utility methods to merge multiple page results
    and extract the full text across the entire document.
    """

    pages: Optional[List[OcrPage]] = None

    def merge(self, other: Optional["OcrDocument"]) -> None:
        """
        Merges another OcrDocument object into this one.
        Ensures that pages are sorted by their page_id.
        """
        if other is None or not other.pages:
            return

        if self.pages is None:
            self.pages = []

        self.pages.extend(other.pages)
        # Sort pages by page_id. Pages with None page_id are placed at the end.
        self.pages.sort(
            key=lambda p: (
                p.page_id is None,
                p.page_id if p.page_id is not None else 0,
            )
        )

    def get_full_text(self, separator: str = "\n\n\n") -> str:
        """
        Concatenates the raw_text of all pages into a single string.
        Used for full-text search and knowledge retrieval.
        """
        if not self.pages:
            return ""

        all_texts: List[str] = []
        for page in self.pages:
            if not page.raw_text:
                continue
            all_texts.append(page.raw_text)

        return separator.join(all_texts)
