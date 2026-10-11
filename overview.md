# Project Guide: OCR Engine (Azure Document Intelligence Mock)

## Project Overview
The **OCR Engine** is a high-fidelity 100% emulator of the **Microsoft Azure AI READ API**. Its primary purpose is to provide a local, self-hosted alternative to Azure Document Intelligence, ensuring that sensitive documents remain entirely within the local infrastructure while maintaining full API compatibility.

The system acts as a distributed pipeline: a REST API frontend accepts documents and coordinates their processing via a background worker. The final output consists of extracted text and a searchable PDF. To enable advanced document management and knowledge retrieval, the text is stored pagewise in LanceDB, allowing for duplicate detection and cross-document knowledge queries.

### Key Technologies
- **Backend Framework**: FastAPI (Python)
- **Task Queue**: RabbitMQ (via `pika`)
- **Storage/Caching**: Redis (for job state and blobs), LanceDB (for vector search and duplicates)
- **OCR Model**: Qwen2.5-VL (via Ollama/local inference)
- **PDF Processing**: PyMuPDF, Pillow
- **Containerization**: Docker & Docker Compose

### System Constraints & Requirements
- **Infrastructure**:
    - REST API and Worker run as separate containers in a Docker stack.
    - State is persisted via Redis 
    - Text content and detected text with bounding boxes are stored in LanceDB pagewise via the worker on the filesystem so that this LanceDB can be used in various LLMs.
    - The system must be resilient to restarts; workers must resume from the last processed command in the queue.
- **Processing Logic**:
    - **Sequentiality**: Only one command is processed at a time (`prefetch=1`).
    - **Format Support**: Must handle PDF, PDF/A, JPG, TIFF, BMP, PNG, GIF.
    - **Resource Management**: Minimal RAM footprint by slicing documents into individual pages and storing them as blobs in Redis.
- **Output Requirements**:
    - **Searchable PDF**: Generation of a PDF with a text layer based on OCR coordinates.
    - **Text Augmentation**: Every extracted page must append a tracking string: `"\n\nOCR JobID: {UUID}"` to facilitate search in Paperless-NGX.
- **Integration**: Designed to be triggered by and integrate with Paperless-NGX.

## Architecture
The system follows a **Command-Based State Machine** architecture:

1. **Ingest Phase (API)**:
   When having received a `Request` then the following sequence needs to happen:
   - receive file as bytes
   - `InputHandler` (Slicing into pages if possible)
   - Creation of a Job in `Redis` (Page Blobs)
   - Creation of a `OcrDocumentCommand` send to `RabbitMQ`
   - Prepare monitoring URL
   - Return monitoring URL to caller

2. **Processing Phase (Worker)**:
   A sequential chain of commands is executed by the worker listening to `RabbitMQ`. Within each step the status of the Job is being updated at the right place. If a step failed, then the `OcrDocumentFailedCommand` is created.
   - `OcrDocumentCommand`: checks for not-processed pages (Loop). Create `OcrPageCommand` if not-processed page was found, `CreateSearchablePdfCommand` otherwise.
   - `OcrPageCommand`: Loads Job from `Redis`, Runs OCR with bounding boxes of single page, Saves Job with intermediate results to `Redis`, creates `OcrPageTextOnlyCommand`.
   - `OcrPageTextOnlyCommand`: Loads Job from `Redis`, Runs OCR without bounding boxes of single page, Saves Job with intermediate results to `Redis`, creates `OcrParseResponseCommand`.
   - `OcrParseResponseCommand`: Loads Job from `Redis`, Runs parsing of single page results, Saves Job with intermediate results to `Redis`, creates `OcrDocumentCommand`.
   - `CreateSearchablePdfCommand`: Loads Job from `Redis`, Runs pdf creation, Saves Job with intermediate results to `Redis`, creates `VectorizeCommand`.
   - `VectorizeCommand`: Loads Job from `Redis`, runs vectorizing, Saves Job with intermediate results to `Redis`, creates `PersistLanceDbCommand`.
   - `PersistLanceDbCommand`: Loads Job from `Redis`, saves Job to LanceDB, creates `OcrDocumentSucceededCommand`.

3. **Completion Phase**:
   `OcrDocumentSucceededCommand` $\rightarrow$ Update Status $\rightarrow$ API provides result via Polling.
   `OcrDocumentFailedCommand` $\rightarrow$ Update Status $\rightarrow$ API provides result via Polling.

## Code Adjustments
- **Existing Tasks**: Once a task is completed, then the task must be updated in the `tasklist.md`. If a more detailed description is possible, it's also okay to add some details into the task description.
- **New Tasks**: If something new shows up, then it must be checked against the Architecture. If the task fits into the Architecture, it needs to be added directly into `tasklist.md` with sufficient details on what to do in which files. If the task does not fit into the Architecture, then the task needs to be discussed and reviewed.
