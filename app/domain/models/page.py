# app/domain/models/page.py
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from app.domain.models.ocr import OcrDocument


class PageInputData(BaseModel):
    """
    Represents a single picture
    """
    page_number: int
    page_width: float
    page_height: float
    page_bytes: Optional[bytes] = None

    intermediate_ocr_page_unparsed_result: Optional[str] = None # result of OCR with bounding boxes
    intermediate_ocr_page_result: Optional[OcrDocument] = None # result of OCR with bounding boxes after parsing
    intermediate_text_result: Optional[str] = None  # result of OCR without bounding boxes
    intermediate_embeddings_result: Optional[List[float]] = None