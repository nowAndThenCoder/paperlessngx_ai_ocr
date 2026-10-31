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
            You are a high-precision OCR system. Extract EVERY visible text (including handwriting) line by line.
            Language: {settings.DOCUMENT_LANGUAGE}.

            OUTPUT FORMAT:
            One line per element: ID: [ymin,xmin,ymax,xmax] Text
            
            RULES:
            1. COORDINATES: [ymin, xmin, ymax, xmax] normalized 0-1000, absolute global position.
            2. IDS: Separate documents get unique integer IDs (1, 2, ...).
            3. PRECISION: Bounding boxes must tightly fit the text.
            4. NO OMISSIONS: Include all notes, handwriting and receipt lines.

            EXAMPLE:
            1: [120,50,135,450] First line of Doc 1
            2: [120,520,135,950] First line of Doc 2

            Start immediately with the first line.\
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
        Parses the compact OCR format: "ID: [ymin,xmin,ymax,xmax] Text"
        """
        if not raw_json_str:
            return OcrDocument(pages=None)

        pages_dict: Dict[int, List[OcrLine]] = {}

        for line in raw_json_str.splitlines():
            line = line.strip()
            if not line or ":" not in line or "[" not in line or "]" not in line:
                continue

            try:
                # Format: "1: [100,20,120,400] Apotheke"
                parts = line.split("]", 1)
                header = parts[0] # "1: [100,20,120,400"
                text_val = parts[1].lstrip(": ").strip()

                # Extract ID and Coordinates
                id_part, coords_part = header.split(":", 1)
                raw_page = int(id_part.strip())
                page_num = raw_page + increase_page_ids_by_offset

                # Clean coords: "[100,20,120,400" -> "100,20,120,400"
                coords_str = coords_part.strip().lstrip("[")
                coords = [int(c.strip()) for c in coords_str.split(",")]
                
                if len(coords) != 4:
                    continue

                ocr_line = OcrLine(
                    text=text_val,
                    ymin=coords[0],
                    xmin=coords[1],
                    ymax=coords[2],
                    xmax=coords[3],
                )

                if page_num not in pages_dict:
                    pages_dict[page_num] = []
                pages_dict[page_num].append(ocr_line)

            except (ValueError, IndexError, TypeError):
                continue

        ocr_pages: List[OcrPage] = []
        for page_num, lines in pages_dict.items():
            ocr_pages.append(OcrPage(page_id=page_num, text_lines=lines))

        ocr_pages.sort(key=lambda p: (p.page_id is None, p.page_id if p.page_id is not None else 0))
        return OcrDocument(pages=ocr_pages if ocr_pages else None)


        # construct the ocr_pages as array containing just the orc_lines
        ocr_pages: List[OcrPage] = []

        # iterates over each keys and their according ocr_lines
        for page_num, lines in pages_dict.items():
            ocr_pages.append(OcrPage(page_id=page_num, text_lines=lines))

        # sort ascending as ocr_pages are not merged by orc_document
        ocr_pages.sort(key=lambda p: (p.page_id is None, p.page_id if p.page_id is not None else 0))

        # returns a collection of orc_documents with the outcome that a n-pages long PDF document can have n+m-ocr_documents
        return OcrDocument(pages=ocr_pages if ocr_pages else None)
