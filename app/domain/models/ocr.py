# app/domain/models/ocr.py
from __future__ import annotations
from typing import List, Optional

from pydantic import BaseModel


class OcrLine(BaseModel):
    """
    Represents a single line of text extracted from a document page.
    The coordinates are normalized (0-1000) relative to the image dimensions,
    as provided by the Vision-Language model.
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

    page_id: Optional[int] = None # if there are more pages on one picture
    text_lines: Optional[List[OcrLine]] = None  # Structured lines with bounding boxes


class OcrDocument(BaseModel):
    """
    A collection of OCR pages forming a complete picture.
    This class provides utility methods to merge multiple page results
    and extract the full text across the entire picture its based on.
    """

    pages: Optional[List[OcrPage]] = None  # if there are more pages on one picture

    def merge(self, other: Optional[OcrDocument]) -> None:
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
