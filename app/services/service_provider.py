import logging
from app.repositories.job_repository import job_repository
from app.services.job_storage_service import job_storage_service
from app.services.pdf_service import PdfService
from app.services.ocr_query_service import OcrQueryService
from app.services.vectorization_service import VectorizationService
from app.services.lancedb_service import LanceDbService
from app.services.rest_client import rest_client
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)

class ServiceProvider:
    """
    Central provider for all application services.
    Ensures that services are instantiated once and shared across commands,
    facilitating easier testing and decoupling.
    """

    def __init__(self):
        self.job_repository = job_repository
        self.job_storage = job_storage_service
        self.ocr_service = OcrQueryService()
        self.pdf_service = PdfService()
        self.vector_service = VectorizationService(rest_client, ollama_client)
        self.lancedb_service = LanceDbService()

# Singleton instance for the application
service_provider = ServiceProvider()
