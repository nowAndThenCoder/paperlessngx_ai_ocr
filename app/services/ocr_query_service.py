import json
import textwrap
from typing import Dict, List, Optional

from app.domain.models.ocr import OcrDocument, OcrLine, OcrPage
from app.services.config import logging
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)


class OcrQueryService:

    @staticmethod
    def get_prompt_with_boxes() -> str:
        from .config import settings

        return textwrap.dedent(f"""\
            You are a high-precision OCR system. Extract absolutely EVERY visible text (including handwriting/signatures) line by line.
            The documents are primarily in {settings.DOCUMENT_LANGUAGE}.

            RULES:
            1. Physically separate documents must be assigned their own document "id" (1, 2, ...).
            2. Do not ignore any handwriting, notes, checkboxes, or receipt lines.
            3. Coordinates [ymin, xmin, ymax, xmax] must be between 0 and 1000 to cover the WHOLE image globally, no matter which document the text belongs to. Do NOT reset coordinates for the second document; use its absolute position on the entire image width.

            SCHEMA (Strict Requirement):
            Return a JSON array of arrays: [id, ymin, xmin, ymax, xmax, "text"]

            EXAMPLE:
            [
            [1, 120,  50, 135, 450, "First line of Doc 1 (left receipt)"],
            [1, 140,  50, 160, 400, "Signature on Doc 1"],
            [2, 120, 520, 135, 950, "First line of Doc 2 (right receipt)"]
            ]

            Start immediately with `[`.\
        """)

    @staticmethod
    def get_prompt_without_boxes() -> str:
        from .config import settings

        return textwrap.dedent(f"""\
            You are a high-precision OCR system for the capture of single documents and multi-document scans.
            The documents are primarily in {settings.DOCUMENT_LANGUAGE}.
            Extract absolutely EVERY visible text (including handwriting, notes, signatures, stamps) following the layout.

            PROCESSING MULTIPLE DOCUMENTS:
            - Carefully examine the image for physically separate documents (e.g., two receipts side-by-side, a receipt on a letter, etc.).
            - If MULTIPLE separate documents are visible, strictly separate the output of EACH document with the line: === DOCUMENT_BREAK ===
            - NEVER interweave or mix texts from different documents.

            STRICT OUTPUT FORMAT RULES:
            1. Output ONLY the recognized text.
            2. Do NOT use Markdown formatting (no # headings, no **bold**, no - bullet points, no table pipes |).
            3. Do NOT use code blocks (no ```-fences).
            4. Do NOT output JSON, XML, or introductory sentences (e.g. FORBIDDEN: "Here is the text:").
            5. Read each document individually from top to bottom and from left to right.
        """)

    def sanitize_response(self, response: str) -> str:
        cleaned_text = response.strip()

        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].lstrip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].lstrip()

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3].rstrip()

        return cleaned_text

    def process_page_with_boxes(self, image_bytes: bytes) -> str:
        prompt = self.get_prompt_with_boxes()
        response = ollama_client.post_generate(image_bytes, prompt)
        sanitized_response = self.sanitize_response(response)
        return sanitized_response

    def process_page_without_boxes(self, image_bytes: bytes) -> str:
        prompt = self.get_prompt_without_boxes()
        response = ollama_client.post_generate(image_bytes, prompt)
        sanitized_response = self.sanitize_response(response)
        return sanitized_response

    def parse_ocr_string_to_document(self, increase_page_ids_by_offset: int, raw_json_str: str) -> OcrDocument:
        """
        Takes the compressed JSON string in Array-in-Array format
        [[page, ymin, xmin, ymax, xmax, text], ...] and converts it
        into the hierarchical OcrDocument structure.
        """
        if not raw_json_str:
            return OcrDocument(pages=None)

        try:
            data: List[List] = json.loads(raw_json_str)
        except json.JSONDecodeError:
            return OcrDocument(pages=None)

        if not isinstance(data, list):
            return OcrDocument(pages=None)

        # hashmap for page-number to Array[OcrLine]
        pages_dict: Dict[int, List[OcrLine]] = {}

        for item in data:
            # Expects the compact format: [page, ymin, xmin, ymax, xmax, "text"]
            if not isinstance(item, list) or len(item) < 6:
                continue

            try:
                raw_page = int(item[0]) if item[0] is not None else 0
                page_num = raw_page + increase_page_ids_by_offset

                ymin_val = int(item[1]) if item[1] is not None else None
                xmin_val = int(item[2]) if item[2] is not None else None
                ymax_val = int(item[3]) if item[3] is not None else None
                xmax_val = int(item[4]) if item[4] is not None else None
                text_val = str(item[5]) if item[5] is not None else ""

                ocr_line = OcrLine(
                    text=text_val,
                    ymin=ymin_val,
                    xmin=xmin_val,
                    ymax=ymax_val,
                    xmax=xmax_val,
                )

                if page_num not in pages_dict:
                    pages_dict[page_num] = []

                pages_dict[page_num].append(ocr_line)

            except (ValueError, TypeError):
                # Safely catches malformed/incomplete lines
                continue

        # construct the ocr_pages as array containing just the orc_lines
        ocr_pages: List[OcrPage] = []

        # iterates over each keys and their according ocr_lines
        for page_num, lines in pages_dict.items():
            ocr_pages.append(OcrPage(page_id=page_num, text_lines=lines))

        # sort ascending as ocr_pages are not merged by orc_document
        ocr_pages.sort(key=lambda p: (p.page_id is None, p.page_id if p.page_id is not None else 0))

        # returns a collection of orc_documents with the outcome that a n-pages long PDF document can have n+m-ocr_documents
        return OcrDocument(pages=ocr_pages if ocr_pages else None)
