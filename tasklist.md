# Implementation Roadmap: OCR Engine

## Target Architecture & Design Principles

### 1. The Command State Machine (The Pipeline)
The system operates as a sequential state machine. A job progresses through a strict chain of commands:
`OcrDocumentCommand` $\rightarrow$ (Loop: `OcrPageCommand` $\rightarrow$ `OcrPageTextOnlyCommand` $\rightarrow$ `OcrParseResponseCommand`) $\rightarrow$ `CreateSearchablePdfCommand` $\rightarrow$ `VectorizeCommand` $\rightarrow$ `PersistLanceDbCommand` $\rightarrow$ `OcrDocumentSucceededCommand`.

### 2. Component Architecture
- **`PdfService`**: Generates a searchable PDF with a hidden text layer using coordinates ($0\text{-}1000$ normalized) provided by the OCR model.
- **`LanceDbService`**: Handles permanent "pagewise" storage on the filesystem, enabling duplicate detection and cross-document queries.
- **`VectorizationService`**: Bridges extracted text to embeddings for vector search.

### 3. Data Lifecycle
- **Transient State (Redis)**: All image blobs, intermediate OCR results, and job metadata live in Redis during processing to minimize disk I/O.
- **Permanent State (LanceDB)**: Data is flushed from Redis to LanceDB only during the `PersistLanceDbCommand` phase.
- **Fixed Interface**: The OCR model (`ocr_query_service.py`) is a fixed black box; no changes are permitted here.

---

## Completed Components
- [x] **Worker Infrastructure**: Sequential processing (`prefetch=1`) and RabbitMQ consumption implemented in `app/main_worker.py`.
- [x] **OCR Interface**: `app/services/ocr_query_service.py` is fully implemented, providing binary-to-text and binary-to-bounding-box functionality.
- [x] **Primary Storage**: Redis-based metadata and blob storage implemented in `app/services/job_storage_service.py`.

---

## Implementation Roadmap

### Phase 1: Component Interface Definition (Architecture)
*Goal: Define the contracts for missing services before coding.*

- [x] **T1.1: Define `PdfService` Interface**
  - **Input**: `OcrPage` objects (with bounding boxes) and raw image bytes from Redis.
  - **Output**: Raw bytes of a searchable PDF.
  - **Functionality**: Mapping normalized $0\text{-}1000$ coordinates to actual page dimensions to create a text layer.
- [x] **T1.2: Define `LanceDbService` Interface**
  - **Input**: Extracted text per page, metadata (JobID, PageID), and embeddings.
  - **Output**: Success/Failure of persistence.
  - **Functionality**: Local filesystem-based storage with a schema optimized for pagewise retrieval.
- [x] **T1.3: Define `VectorizationService` Interface**
  - **Input**: Extracted page text.
  - **Output**: Vector embeddings.
  - **Functionality**: Integration with the chosen embedding model.

### Phase 2: Support Service Implementation
*Goal: Implement the services defined in Phase 1.*

- [x] **T2.1: Implement `PdfService`**
  - **Implementation**: Use PyMuPDF/Pillow.
  - **Requirement**: Correct coordinate transformation from $0\text{-}1000$ to PDF points.
- [x] **T2.2: Implement `LanceDbService`**
  - **Implementation**: Setup local LanceDB table.
  - **Requirement**: Ensure "pagewise" storage and support for duplicate detection.
- [x] **T2.3: Implement `VectorizationService`**
  - **Implementation**: Integration of the embedding logic.

### Phase 3: Command Logic Implementation (The State Machine)
*Goal: Fill the empty `execute()` methods in `app/domain/commands.py`.*

- [x] **T3.1: Implement `OcrDocumentCommand`**
  - **Logic**: Check `Job` for unprocessed pages. If found $\rightarrow$ create `OcrPageCommand`. If all processed $\rightarrow$ create `CreateSearchablePdfCommand`.
- [x] **T3.2: Implement `OcrPageCommand`**
  - **Logic**: Load image blob $\rightarrow$ Call `ocr_service.process_page_with_boxes` $\rightarrow$ Save intermediate result to Redis $\rightarrow$ Create `OcrPageTextOnlyCommand`.
- [x] **T3.3: Implement `OcrPageTextOnlyCommand`**
  - **Logic**: Load image blob $\rightarrow$ Call `ocr_service.process_page_without_boxes` $\rightarrow$ Save result to Redis $\rightarrow$ Create `OcrParseResponseCommand`.
- [x] **T3.4: Implement `OcrParseResponseCommand`**
  - **Logic**: Process raw OCR output into `OcrDocument` structure $\rightarrow$ Save to Redis $\rightarrow$ Create `OcrDocumentCommand` (to check for next page).
- [x] **T3.5: Implement `CreateSearchablePdfCommand`**
  - **Logic**: Invoke `PdfService` using aggregated Redis results $\rightarrow$ Save final PDF bytes to Redis $\rightarrow$ Create `VectorizeCommand`.
- [x] **T3.6: Implement `VectorizeCommand`**
  - **Logic**: Invoke `VectorizationService` for all pages $\rightarrow$ Save embeddings to Redis $\rightarrow$ Create `PersistLanceDbCommand`.
- [x] **T3.7: Implement `PersistLanceDbCommand`**
  - **Logic**: Invoke `LanceDbService` to move text and embeddings from Redis to Disk $\rightarrow$ Create `OcrDocumentSucceededCommand`.
- [x] **T3.8: Implement `OcrDocumentSucceededCommand` & `OcrDocumentFailedCommand`**
  - **Logic**: Update `JobStatus` to `SUCCEEDED` or `FAILED` and log final timestamps.

### Phase 4: Testing Framework & Quality Assurance
*Goal: Establish a professional, multi-layered testing strategy to ensure pipeline reliability.*

- [ ] **T4.1: Setup Testing Infrastructure**
  - **Framework**: Implement `pytest` as the primary test runner.
  - **BDD Integration**: Integrate `pytest-bdd` to allow Gherkin-style feature files (Given/When/Then) for high-level pipeline validation.
  - **Mocking**: Setup `unittest.mock` or `pytest-mock` to isolate components from Redis/RabbitMQ during unit tests.
- [ ] **T4.2: Service Layer Unit Tests**
  - **`PdfService`**: Validate coordinate transformation (0-1000 $\rightarrow$ PDF points) and PDF generation.
  - **`LanceDbService`**: Validate persistence, retrieval, and duplicate detection.
  - **`VectorizationService`**: Validate embedding retrieval and error handling.
- [ ] **T4.3: Command-Level State Machine Tests**
  - **Logic**: For EVERY command, test the `execute()` result and the `create_next_command()` transition.
  - **Branch Testing**: Specifically test all "exit" paths (e.g., if `OcrDocumentCommand` finds no more pages $\rightarrow$ verify it triggers `CreateSearchablePdfCommand`).
  - **Failure Modes**: Test how each command handles missing data in Redis or service timeouts.
- [ ] **T4.4: End-to-End (E2E) Pipeline Integration**
  - **Scenario**: Trigger a full job $\rightarrow$ Verify final Searchable PDF $\rightarrow$ Verify LanceDB entries.
  - **Gherkin Feature**: Create a `.feature` file describing the "Happy Path" and "Known Error" paths.
- [ ] **T4.5: Refactor `test.py` & Data Management**
  - **Clean-up**: Transform `test.py` from a script into a suite of pytest tests.
  - **Data Organization**: Utilize the `test/data/` folder for standardized input/output golden files.

### Phase 5: API Compatibility & Integration
*Goal: Ensure 100% emulation of the Azure AI READ API for Paperless-NGX integration.*

- [ ] **T5.1: Azure AI READ API Compatibility Audit & Refinement**
  - **Logic**: Compare `app/main_restapi.py` against official Microsoft Azure AI READ API specifications.
  - **Requirement**: Verify and fix response headers, error codes, JSON structures, and polling behavior.
  - **Goal**: Ensure that Paperless-NGX can use the engine without modification, allowing for the bulk re-processing of existing documents to populate LanceDB.

### Phase 6: Stability, Maintainability & Code Quality
*Goal: Harden the system for production use and ensure high code standards.*

- [ ] **T6.1: Resolve Critical Runtime Bugs**
  - **Logic**: Fix undefined variables in `main_restapi.py` and `main_worker.py`. Resolve missing dependencies (e.g., `JobDispatcher`).
  - **Requirement**: Zero `NameError` or `ImportError` during a full pipeline run.
- [ ] **T6.2: Improve Error Handling & Observability**
  - **Logic**: Replace silent `try...except` blocks in `commands.py` with detailed logging using `logger.exception()`.
  - **Requirement**: Every failure in the pipeline must leave a traceable log entry with a stack trace.
- [ ] **T6.3: Decouple Command Dependencies**
  - **Logic**: Move service instantiation out of `execute()` methods in `commands.py` to reduce tight coupling (Dependency Injection).
  - **Requirement**: Commands should receive required services as dependencies.
- [ ] **T6.4: Workspace-wide Pylance Audit & Cleanup**
  - **Logic**: Scan all `.py` files for Pylance errors, warnings, and type mismatches.
  - **Requirement**: Resolve all diagnostics to achieve a "clean" editor state.
