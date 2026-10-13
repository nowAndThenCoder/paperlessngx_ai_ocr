import logging
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Docker ENV Variables
    LOG_LEVEL: str = Field(default="INFO", description="LogLevel e.g. DEBUG, INFO")
    REDIS_HOST: str = Field(default="localhost", description="Redis Hostname / Container Name")
    REDIS_PORT: int = Field(default=6379, description="Redis Port")
    RABBITMQ_HOST: str = Field(default="localhost", description="RabbitMQ Hostname / Container Name")
    RABBITMQ_QUEUE_NAME: str = "ocr_job_tasks"
    RABBITMQ_ERROR_QUEUE_NAME: str = "ocr_job_errors"

    OLLAMA_URL: str = Field(default="http://localhost:11434", description="Ollama API URL")
    OLLAMA_MODEL_VL: str = Field(default="vision-model:latest", description="Vision Model used")
    OLLAMA_MODEL_TEXTEMBED: str = Field(default="nomic-embed-text", description="Text Embedding Model used")
    OLLAMA_TIMEOUT: int = Field(default=4800, description="Timeout for Ollama requests in seconds")
    OLLAMA_DPI: int = Field(default=300, description="DPI for PDF page rendering")
    LANCEDB_DATA_DIR: str = Field(default="./lancedb_data", description="Path to LanceDB data directory")
    DOCUMENT_LANGUAGE: str = Field(default="German", description="Primary language of documents to be processed")

    MAX_PARALLEL_JOBS: int = Field(default=1, description="Maximum number of parallel jobs")
    MAX_THREADS_PER_JOB: int = Field(default=1, description="Maximum threads per job")
    PYTHONUNBUFFERED: int = Field(default=1, description="Python Unbuffered Output Flag")

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # Pydantic v2 Settings Configuration
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()

log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

# Format: Date | Thread | Level (8 chars aligned) | Logger-Name (30 chars aligned) | Message
LOG_FORMAT_DEF = "%(asctime)s.%(msecs)03d [%(threadName)15.15s] %(levelname)-5s %(name)-30.30s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(fmt=LOG_FORMAT_DEF, datefmt=DATE_FORMAT)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

logging.getLogger().setLevel(log_level)
logging.getLogger().handlers.clear()
logging.getLogger().addHandler(console_handler)
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
