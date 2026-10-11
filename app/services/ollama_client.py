import base64
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .config import logging, settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, session=None):
        # Use provided session or create a new one with retries
        if session:
            self.session = session
        else:
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

    def post_generate(self, image_bytes: bytes, prompt: str) -> str:
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
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

    def post_embeddings(self, prompt: str) -> List[float]:
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

    def check_health(self) -> bool:
        try:
            url = settings.OLLAMA_URL.rstrip('/')
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"Ollama health check failed: {e}")
            return False


ollama_client = OllamaClient()
