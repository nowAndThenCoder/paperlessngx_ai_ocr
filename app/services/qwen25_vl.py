import json
import textwrap
from typing import Any, Dict, List, Optional

from app.domain.models.ocr import OcrDocument, OcrLine, OcrPage
from app.services.config import logging
from app.services.rest_client import rest_client

logger = logging.getLogger(__name__)


class Qwen25VlQuery:

    @staticmethod
    def get_prompt_with_boxes() -> str:
        from .config import settings

        return textwrap.dedent(f"""\
            You are a high-precision OCR system. Extract absolutely EVERY visible text (including handwriting/signatures) line by line.
            The documents are primarily in {settings.DOCUMENT_LANGUAGE}.

            RULES:
            1. Physically separate documents must be assigned their own "page" number (1, 2, ...).
            2. Do not ignore any handwriting, notes, checkboxes, or receipt lines.
            3. Coordinates [ymin, xmin, ymax, xmax] must be between 0 and 1000.

            SCHEMA (Strict Requirement):
            Return a JSON array of arrays: [page, ymin, xmin, ymax, xmax, "text"]

            EXAMPLE:
            [
            [1, 120, 50, 135, 450, "First line of Doc 1"],
            [1, 140, 50, 160, 400, "Signature Mr. Sample"],
            [2, 120, 520, 135, 950, "First line of Doc 2"]
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
        logger.info(f"processing started")
        prompt = self.get_prompt_with_boxes()
        response = rest_client.post_ollama_generate(image_bytes, prompt)
        sanitized_response = self.sanitize_response(response)
        logger.info(f"processing finished")
        return sanitized_response

    def process_page_without_boxes(self, image_bytes: bytes) -> str:
        logger.info(f"processing started")
        prompt = self.get_prompt_without_boxes()
        response = rest_client.post_ollama_generate(image_bytes, prompt)
        sanitized_response = self.sanitize_response(response)
        logger.info(f"processing finished")
        return sanitized_response

    def parse_ocr_string_to_document(self, increase_page_ids_by_offset: int, raw_json_str: str) -> OcrDocument:
        """
        Nimmt den komprimierten Qwen-JSON-String Array-in-Array an
        [[page, ymin, xmin, ymax, xmax, text], ...] und konvertiert ihn
        in die hierarchische OcrDocument-Struktur.
        """
        if not raw_json_str:
            return OcrDocument(pages=None)

        try:
            data: Any = json.loads(raw_json_str)
        except json.JSONDecodeError:
            return OcrDocument(pages=None)

        if not isinstance(data, list):
            return OcrDocument(pages=None)

        # hashmap for page-number to Array[OcrLine]
        pages_dict: Dict[int, List[OcrLine]] = {}

        for item in data:
            # Erwartet das Kompaktformat: [page, ymin, xmin, ymax, xmax, "text"]
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
                # Fängt fehlerhafte/unvollständige Zeilen sicher ab
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

    # TODO this function needs double checking
    def convert_to_azure_json(
        self, ocr_doc: Optional[OcrDocument], img_width: int = 1000, img_height: int = 1000
    ) -> Dict[str, Any]:
        """
        Transformiert das OcrDocuments-Objekt in das Azure AI Read API JSON-Schema.
        """
        blocks: List[Dict[str, Any]] = []

        if not ocr_doc or not ocr_doc.pages:
            return {
                "modelVersion": "2024-02-01",
                "metadata": {"width": img_width, "height": img_height},
                "readResult": {"blocks": []},
            }

        for page in ocr_doc.pages:
            if not page.text_lines:
                continue

            lines: List[Dict[str, Any]] = []
            for line in page.text_lines:
                ymin = line.ymin if line.ymin is not None else 0
                xmin = line.xmin if line.xmin is not None else 0
                ymax = line.ymax if line.ymax is not None else ymin + 10
                xmax = line.xmax if line.xmax is not None else xmin + 10

                # Skalierung von Qwen-Normkoordinaten (0-1000) auf Pixel-Dimensionen
                x1 = int(xmin * img_width / 1000)
                y1 = int(ymin * img_height / 1000)
                x2 = int(xmax * img_width / 1000)
                y2 = int(ymax * img_height / 1000)

                polygon = [
                    {"x": x1, "y": y1},
                    {"x": x2, "y": y1},
                    {"x": x2, "y": y2},
                    {"x": x1, "y": y2},
                ]

                text_content = line.text if line.text is not None else ""

                word = {
                    "text": text_content,
                    "boundingPolygon": polygon,
                    "confidence": 0.99,
                }

                lines.append({"text": text_content, "boundingPolygon": polygon, "words": [word]})

            if lines:
                blocks.append({"lines": lines})

        return {
            "modelVersion": "2024-02-01",
            "metadata": {"width": img_width, "height": img_height},
            "readResult": {"blocks": blocks},
        }
