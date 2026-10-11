# app/domain/models/page.py
import base64
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.models.ocr import OcrDocument


class PageInputData(BaseModel):
    page_number: int
    page_width: float
    page_height: float
    page_bytes_base64: Optional[str] = Field(default=None)

    intermediate_result: Optional[str] = None
    ocr_page_result: Optional["OcrDocument"] = None

    @property
    def page_bytes(self) -> Optional[bytes]:
        if not self.page_bytes_base64:
            return None
        return base64.b64decode(self.page_bytes_base64)

    @page_bytes.setter
    def page_bytes(self, value: Optional[bytes]) -> None:
        if value is None:
            self.page_bytes_base64 = None
        else:
            self.page_bytes_base64 = base64.b64encode(value).decode("utf-8")
