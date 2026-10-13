from typing import Optional
import time
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from uuid import UUID

from app.services.config import logging
from app.domain.models.job import JobStatus
from app.repositories.job_repository import job_repository
from app.services.job_dispatcher import JobDispatcher
from app.services.ocr_query_service import OcrQueryService
from app.services.rest_client import rest_client
from app.services.ollama_client import ollama_client
from app.services.input_handler import InputHandler
from app.domain.commands import OcrDocumentCommand

app = FastAPI(
    title="OCR Engine REST API (Azure Document Intelligence Mock)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

logger = logging.getLogger(__name__)
ocr_service = OcrQueryService()
job_dispatcher = JobDispatcher()
input_handler = InputHandler()


@app.post(
    "/documentintelligence/documentModels/{model_id}:analyze",
    status_code=202,
    summary="Entry URL for OCR execution on documents",
)
async def analyze_document(
    model_id: str,
    request: Request,
    content_type: Optional[str] = Header(None, alias="Content-Type"),
    api_version: str = Query("2023-07-31", alias="api-version"),
):
    try:
        body_bytes = await request.body()
        file_bytes = rest_client.fetch_file_bytes_from_request(content_type or "", body_bytes)
        file_type = rest_client.get_file_type_of_bytes(file_bytes)

        # 1. Split file into pages and persist the Job
        pages = input_handler.split_file(file_bytes, file_type)
        if not pages:
            raise HTTPException(status_code=400, detail="Could not parse file into pages.")

        # Prepare metadata for source pages (dimensions) to be stored in Job meta
        source_pages_meta = [
            {"page_num": p[0], "width": p[2], "height": p[3]} 
            for p in pages
        ]

        # Create and save the job entity with source pages meta
        job = job_repository.create_job(
            file_type=file_type, 
            total_pages=len(pages), 
            file_name=f"upload_{int(time.time())}",
            source_pages_data=source_pages_meta
        )
        
        # Save page images to storage
        for page_num, page_bytes, _, _ in pages:
            job_repository.save_page_image(job.job_id, page_num, page_bytes)

        # 2. Start the pipeline by dispatching the first command
        first_command = OcrDocumentCommand(job_id=job.job_id)
        job_dispatcher.dispatch(first_command)

        # create polling URL
        job_id = job.job_id
        base_url = str(request.base_url).rstrip("/")
        polling_url = f"{base_url}/documentintelligence/documentModels/{model_id}/analyzeResults/{job_id}?api-version={api_version}"

        return Response(
            status_code=202,
            headers={
                "Operation-Location": polling_url,
                "Access-Control-Expose-Headers": "Operation-Location",
            },
        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"internal error: {str(e)}")


@app.get(
    "/documentintelligence/documentModels/{model_id}/analyzeResults/{job_id}",
    summary="Polling endpoint for status & OCR JSON result",
)
async def get_analysis_result(
    model_id: str,
    job_id: str,
    api_version: str = Query("2023-07-31", alias="api-version"),
):
    try:
        parsed_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid Job ID format: {job_id}")

    # TODO get job from redis
    from app.repositories.job_repository import job_repository
    job = job_repository.find_by_id(parsed_uuid)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    # Status: RUNNING or NOT_STARTED
    if job.status != JobStatus.FAILED and job.status != JobStatus.SUCCEEDED:
        job_status_text = job.status.to_friendly_string()
        return JSONResponse(
            status_code=200,
            content={
                "status": job_status_text,
                "createdDateTime": job.created_at,
                "lastUpdatedDateTime": job.updated_at,
                "percentCompleted": job.get_completion_percentage(),
            },
        )
    elif job.status == JobStatus.FAILED:
        return JSONResponse(
            status_code=200,
            content={
                "status": "failed",
                "createdDateTime": job.created_at,
                "lastUpdatedDateTime": job.updated_at,
                "error": {
                    "code": "InternalServerError",
                    "message": getattr(job, "error_message", None) or "Unknown error during OCR processing.",
                },
            },
        )
    else:
        # Status: SUCCEEDED -> Assemble Azure AI Read JSON
        merged_docs = OcrDocuments(pages=[])
        for page in job.source_pages or []:
            if page.ocr_page_result:
                merged_docs.merge(page.ocr_page_result)

        first_page = job.source_pages[0] if job.source_pages else None
        width = int(first_page.page_width) if first_page else 1000
        height = int(first_page.page_height) if first_page else 1000

        analyze_result = ocr_service.convert_ocr_documents_to_azure_json(
            merged_docs, img_width=width, img_height=height
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "succeeded",
                "createdDateTime": job.created_at,
                "lastUpdatedDateTime": job.updated_at,
                "analyzeResult": analyze_result,
            },
        )


@app.get(
    "/documentintelligence/documentModels/{model_id}/analyzeResults/{job_id}/pdf",
    summary="Download of the processed PDF file",
)
async def get_analyze_result_pdf(
    model_id: str,
    job_id: str,
    api_version: str = Query("2023-07-31", alias="api-version"),
):
    """Download endpoint for the generated searchable PDF (once CreatePdfTask is complete)."""
    try:
        parsed_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid Job ID format: {job_id}")

    job = job_repository.find_by_id(parsed_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not yet complete (Current status: {job.status.value}).",
        )

    # Prefers final_pdf_bytes generated in step 3, otherwise fallback
    # pdf_bytes = job.final_pdf_bytes or (
    #    job.source_pages[0].page_bytes if job.source_pages and job.source_pages[0].page_bytes else None
    # )

    pdf_bytes = None

    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="No PDF bytes available for this job.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="searchable_{job_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
