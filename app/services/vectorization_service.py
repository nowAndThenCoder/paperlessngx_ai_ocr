# app/services/vectorization_service.py
import logging
from typing import List

from .rest_client import RestClient
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class VectorizationService:
    """
    Service for converting extracted text into vector embeddings.
    Bridges extracted text to embeddings for vector search in LanceDB.
    """

    def __init__(self, rest_client: RestClient, ollama_client: OllamaClient):
        self.rest_client = rest_client
        self.ollama_client = ollama_client

    def vectorize_text(self, text: str) -> List[float]:
        """
        Converts the provided text into a vector embedding using Ollama.

        Args:
            text: The extracted text from a page.

        Returns:
            A list of floats representing the vector embedding.
        """
        try:
            embeddings = self.ollama_client.post_embeddings(text)
            if not embeddings:
                logger.warning(f"Ollama returned empty embeddings for text: {text[:50]}...")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to vectorize text: {e}")
            # Return a zero-vector as fallback to avoid breaking the pipeline
            # (Assuming the embedding dimension is known or handled by LanceDB)
            raise RuntimeError(f"Vectorization failed: {e}") from e
