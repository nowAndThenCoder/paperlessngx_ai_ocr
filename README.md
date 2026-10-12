# OCR Engine (Azure Document Intelligence Mock)

A high-fidelity, self-hosted emulator of the **Microsoft Azure AI READ API**. This engine allows organizations to maintain complete control over their sensitive documents by replacing cloud-based OCR services with a local pipeline, while maintaining 100% API compatibility for seamless integration with tools like **Paperless-NGX**.

## Project Overview
The **OCR Engine** provides a local, self-hosted alternative to Azure Document Intelligence. It acts as a distributed pipeline where a REST API frontend accepts documents and coordinates their processing via a background worker. The final output consists of extracted text and a searchable PDF. To enable advanced document management and knowledge retrieval, the text is stored pagewise in LanceDB, allowing for duplicate detection and cross-document knowledge queries.

## Key Features

- **Azure API Emulation**: Full compatibility with the Azure AI READ API specifications.
- **Advanced OCR Pipeline**: Leverages high-precision Vision-Language models for text and bounding box extraction.
- **Searchable PDFs**: Automatically generates PDFs with an invisible text layer based on normalized OCR coordinates.
- **Pagewise Vector Storage**: Stores extracted text and embeddings in **LanceDB**, enabling efficient duplicate detection and cross-document semantic search.
- **Distributed Architecture**: Decoupled REST API and Worker nodes coordinated via **RabbitMQ**.
- **Transient State Management**: Uses **Redis** for high-performance blob and metadata storage during processing.

## Architecture

The system is designed as a **Command-Based State Machine**. Every document processing job follows a strict sequential pipeline across three main phases:

### 1. Ingest Phase (API)
When a request is received, the following sequence occurs:
- Receive file as bytes.
- `InputHandler`: Slicing into pages if possible.
- Creation of a Job in `Redis` (storing Page Blobs).
- Creation of a `OcrDocumentCommand` sent to `RabbitMQ`.
- Prepare and return a monitoring URL to the caller.

### 2. Processing Phase (Worker)
A sequential chain of commands is executed by the worker. If a step fails, an `OcrDocumentFailedCommand` is created.
- `OcrDocumentCommand`: Checks for unprocessed pages. Creates `OcrPageCommand` if a page is found, otherwise proceeds to `CreateSearchablePdfCommand`.
   - `OcrPageCommand`: Loads Job from `Redis`, runs OCR with bounding boxes for a single page, saves results to `Redis`, and creates `OcrPageTextOnlyCommand`.
   - `OcrPageTextOnlyCommand`: Loads Job from `Redis`, runs OCR without bounding boxes for a single page, saves results to `Redis`, and creates `OcrParseResponseCommand`.
   - `OcrParseResponseCommand`: Loads Job from `Redis`, parses single page results, saves results to `Redis`, and creates `OcrDocumentCommand` (to check for next pages).
- `CreateSearchablePdfCommand`: Loads Job from `Redis`, generates the searchable PDF, saves results to `Redis`, and creates `VectorizeCommand`.
- `VectorizeCommand`: Loads Job from `Redis`, performs vectorization, saves results to `Redis`, and creates `PersistLanceDbCommand`.
- `PersistLanceDbCommand`: Loads Job from `Redis`, persists data to LanceDB, and creates `OcrDocumentSucceededCommand`.

### 3. Completion Phase
- `OcrDocumentSucceededCommand` $\rightarrow$ Update Status $\rightarrow$ API provides result via Polling.
- `OcrDocumentFailedCommand` $\rightarrow$ Update Status $\rightarrow$ API provides result via Polling.

## System Constraints & Requirements

### Infrastructure
- **Deployment**: REST API and Worker run as separate containers in a Docker stack.
- **State**: Persisted via Redis.
- **Storage**: Text content and detected text with bounding boxes are stored in LanceDB pagewise on the filesystem to be accessible by various LLMs.
- **Resilience**: System must be resilient to restarts; workers must resume from the last processed command in the queue.

### Processing Logic
- **Sequentiality**: Only one command is processed at a time (`prefetch=1`).
- **Format Support**: Handles PDF, PDF/A, JPG, TIFF, BMP, PNG, GIF.
- **Resource Management**: Minimal RAM footprint by slicing documents into individual pages and storing them as blobs in Redis.

### Output Requirements
- **Searchable PDF**: Generation of a PDF with a text layer based on OCR coordinates.
- **Text Augmentation**: Every extracted document must append a tracking string: `"\n\nOCR JobID: {UUID}"` to facilitate search in Paperless-NGX.
- **Integration**: Specifically designed to be triggered by and integrate with Paperless-NGX.

## Tech Stack
- **Backend**: FastAPI (Python)
- **Task Queue**: RabbitMQ (pika)
- **Caching/Transient State**: Redis
- **Vector Database**: LanceDB
- **OCR Model**: Configurable Vision-Language Model (via Ollama)
- **PDF Processing**: PyMuPDF, Pillow

## Getting Started

### Prerequisites
- **Ollama**: Installed and running with the configured VL and embedding models.
- **Redis**: Running instance.
- **RabbitMQ**: Running instance.
- **Python 3.10+**

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
- `OLLAMA_MODEL_VL`: Vision model for OCR (default: `vision-model:latest`).
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
├── scripts                # Developments scripts
```

## License
This project is licensed under the MIT License - see the LICENSE file for details.

