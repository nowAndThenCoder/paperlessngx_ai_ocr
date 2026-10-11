import base64
import json
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.domain.models.job import FileType
from .config import logging, settings

logger = logging.getLogger(__name__)


class RestClient:
    def __init__(self):
        # create connection with connection pooling and automatic retries
        self.session = requests.Session()

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def post_ollama_generate(self, image_bytes: bytes, prompt: str) -> str:
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        """Sendet einen Request an die Ollama API, um basierend auf einem Bild und Prompt eine Antwort zu generieren.
        
        Args:
            img_b64 (str): Das Bild im Base64-kodierten Format.
            prompt (str): Der Text-Prompt für das Vision-Modell.

        Returns:
            str: Die generierte Antwort des Modells als Text.

        Raises:
            RuntimeError: Wenn ein Fehler bei der API-Anfrage auftritt.
        """
        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL_VL,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
                "num_ctx": 65536,
                "num_predict": 65536,
            },
        }

        try:
            response = self.session.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT)
            response.raise_for_status()
            return response.json().get("response", "")

        except requests.RequestException as e:
            error_msg = f"Ollama API Error: {e}"
            resp = getattr(e, "response", None)
            if resp is not None:
                error_msg += f" | Body: {resp.text}"

            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def post_ollama_embeddings(self, prompt: str) -> List[float]:
        """Sends a request to the Ollama API to generate an embedding for the given text.

        Args:
            prompt (str): The text to embed.

        Returns:
            List[float]: The vector embedding.

        Raises:
            RuntimeError: If the API request fails.
        """
        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/embeddings"
        payload = {
            "model": settings.OLLAMA_MODEL_TEXTEMBED,
            "prompt": prompt,
        }

        try:
            response = self.session.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT)
            response.raise_for_status()
            return response.json().get("embedding", [])

        except requests.RequestException as e:
            error_msg = f"Ollama Embeddings API Error: {e}"
            resp = getattr(e, "response", None)
            if resp is not None:
                error_msg += f" | Body: {resp.text}"

            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def fetch_file_bytes_from_request(self, content_type: str, body_bytes: bytes) -> bytes:
        """fetches the binary content from the request

        Args:
            content_type (str): _content type_
            body_bytes (bytes): _content of the body in bytes_

        Raises:
            ValueError: _when no bytes are received_
            ValueError: _when body is defined as json but actually is not_
            ValueError: _when body is defined as json but has no attributes 'base64Source' nor 'source'
            ValueError: _when source data are not decodable as base64_

        Returns:
            bytes: _bytes of the request_
        """
        if not body_bytes:
            raise ValueError("No bytes in the body received")

        if "application/json" not in content_type.lower():
            return body_bytes

        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error with treating body as json: {e}")
            raise ValueError(f"Error with treating body as json: {e}") from e

        # content is json and can be treated as such
        if "base64Source" in body_json:
            source_data = body_json["base64Source"]
        elif "source" in body_json:
            source_data = body_json["source"]
        else:
            raise ValueError("Error obtaining binary data via 'base64Source' nor 'source'")

        # binary data will be decoded now
        try:
            return base64.b64decode(source_data)
        except Exception as e:
            logger.error(f"Error decoding Base64-data: {e}")
            raise ValueError(f"Error decoding Base64-data: {e}") from e

    def get_file_type_of_bytes(self, binary_data: bytes) -> FileType:
        if binary_data.startswith(b"%PDF"):
            file_type = FileType.PDF
        elif binary_data.startswith(b"\x89PNG"):
            file_type = FileType.PNG
        elif binary_data.startswith(b"\xff\xd8\xff"):
            file_type = FileType.JPEG
        elif binary_data.startswith(b"II*\x00") or binary_data.startswith(b"MM\x00*"):
            file_type = FileType.TIFF
        elif binary_data.startswith(b"BM"):
            file_type = FileType.BMP
        elif binary_data.startswith(b"RIFF") and len(binary_data) >= 12 and binary_data[8:12] == b"WEBP":
            file_type = FileType.WEBP
        else:
            file_type = FileType.UNKNOWN

        return file_type


rest_client = RestClient()
