# OCR Engine (Azure Document Intelligence Mock)

A high-fidelity, self-hosted emulator of the **Microsoft Azure AI READ API**. This engine allows organizations to maintain complete control over their sensitive documents by replacing cloud-based OCR services with a local pipeline, while maintaining 100% API compatibility for seamless integration with tools like **Paperless-NGX**.

## Key Features

- **Azure API Emulation**: Full compatibility with the Azure AI READ API specifications.
- **Advanced OCR Pipeline**: Leverages the **Qwen2.5-VL** model for high-precision text and bounding box extraction.
- **Searchable PDFs**: Automatically generates PDFs with an invisible text layer based on normalized OCR coordinates.
- **Pagewise Vector Storage**: Stores extracted text and embeddings in **LanceDB**, enabling efficient duplicate detection and cross-document semantic search.
- **Distributed Architecture**: Decoupled REST API and Worker nodes coordinated via **RabbitMQ**.
- **Transient State Management**: Uses **Redis** for high-performance blob and metadata storage during processing.

## Architecture

The system is designed as a **Command-Based State Machine**. Every document processing job follows a strict sequential pipeline:

`OcrDocumentCommand` $\rightarrow$ (`OcrPageCommand` $\rightarrow$ `OcrPageTextOnlyCommand` $\rightarrow$ `OcrParseResponseCommand`) $\rightarrow$ `CreateSearchablePdfCommand` $\rightarrow$ `VectorizeCommand` $\rightarrow$ `PersistLanceDbCommand` $\rightarrow$ `OcrDocumentSucceededCommand`.

### Tech Stack
- **Backend**: FastAPI (Python)
- **Task Queue**: RabbitMQ (pika)
- **Caching/Transient State**: Redis
- **Vector Database**: LanceDB
- **OCR Model**: Qwen2.5-VL (via Ollama)
- **PDF Processing**: PyMuPDF, Pillow

## Getting Started

### Prerequisites
- **Ollama**: Installed and running with the `qwen2.5-vl` and `nomic-embed-text` models.
- **Redis**: Running instance.
- **RabbitMQ**: Running instance.
- **Python 3.10+** (tested with Python 3.14)

### Production Deployment (Recommended)

For stable and scalable deployment, the system is designed to be run as a **Docker Stack**.

1. **Configuration**:
   Set the required environment variables (see the Configuration section below) in your `.env` file or Docker Compose environment.

2. **Deployment**:
   Use the configuration files in the `docker/` directory:
   ```bash
   cd docker
   docker-compose up -d
   ```

### Local Development

This section is intended for developers who wish to modify the code or run the system without Docker for faster iteration and debugging.

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ocr_engine
   ```

2. **Environment Setup**:
   Use the provided setup scripts to create a virtual environment and install dependencies for local testing.
   - **Windows**:
     ```powershell
     .\scripts\setup.ps1
     ```
   - **Linux/macOS**:
     ```bash
     chmod +x scripts/setup.sh
     ./scripts/setup.sh
     ```

3. **Running the System**:
   Start the components manually:
   - **Worker**: 
     - Windows: `.\scripts\run_worker.ps1`
     - Linux: `python -m app.main_worker`
   - **API Server**: 
     - Windows: `.\scripts\run_server.ps1`
     - Linux: `python -m uvicorn app.main_restapi:app --host 0.0.0.0 --port 5000`

### Configuration
The engine is configured via environment variables. You can find the defaults in `app/services/config.py`. Key variables include:
- `LOG_LEVEL`: Log level (e.g., DEBUG, INFO).
- `REDIS_HOST` / `REDIS_PORT`: Redis connection details.
- `RABBITMQ_HOST`: RabbitMQ connection details.
- `OLLAMA_URL`: URL of your Ollama instance.
- `OLLAMA_MODEL_VL`: Vision model for OCR (default: `qwen2.5vl:7b`).
- `OLLAMA_MODEL_TEXTEMBED`: Embedding model for vectorization (default: `nomic-embed-text`).
- `OLLAMA_TIMEOUT`: Timeout for Ollama requests in seconds.
- `OLLAMA_DPI`: DPI for PDF page rendering.
- `LANCEDB_DATA_DIR`: Local path for permanent storage.
- `DOCUMENT_LANGUAGE`: Primary language of documents (e.g., "German").
- `MAX_PARALLEL_JOBS` / `MAX_THREADS_PER_JOB`: Concurrency settings.

## Project Structure

```text
ocr_engine/
├── app/
│   ├── domain/
│   │   ├── commands/      # State machine command logic
│   │   └── models/        # Domain entities (Job, OcrDocuments, etc.)
│   ├── repositories/      # Data access layer
│   └── services/          # Business logic (OCR, PDF, Vectorization, Storage)
├── docker/                # Docker configuration (Dockerfile, compose.yml)
├── test/                  # Unit and integration tests
├── requirements.txt       # Python dependencies
├── setup.ps1/setup.sh     # Environment setup scripts
└── overview.md            # Detailed architecture guide
```

## License
This project is licensed under the MIT License - see the LICENSE file for details.
