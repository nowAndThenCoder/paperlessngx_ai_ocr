from typing import Optional
import time
import json
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

from app.services.document_input_service import DocumentInputService
from app.domain.commands import OcrDocumentCommand
from app.domain.models.ocr import OcrDocument
from app.services.azure_ai_result_generator import AzureAIResultGenerator
from app.services.response_factory import response_factory

app = FastAPI(
    title="OCR Engine REST API (Azure Document Intelligence Mock)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

logger = logging.getLogger(__name__)
ocr_service = OcrQueryService()
job_dispatcher = JobDispatcher()
input_handler = DocumentInputService()
azure_result_gen = AzureAIResultGenerator()


@app.post("/documentintelligence/documentModels/{model_id}:analyze", status_code=202, summary="Entry URL for OCR execution on documents")
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

        # Split file into pages and persist the Job
        pageInputDataList = input_handler.split_file(file_bytes, file_type)
        if not pageInputDataList:
            raise HTTPException(status_code=400, detail="Could not parse file into pages.")

        # Create and save the job entity with source pages meta
        job = job_repository.create_job(
            file_type=file_type, 
            source_pages_data=pageInputDataList
        )

        # Start the pipeline by dispatching the first command
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


@app.get("/documentintelligence/documentModels/{model_id}/analyzeResults/{job_id}", summary="Polling endpoint for status & OCR JSON result")
async def get_analysis_result(
    model_id: str,
    job_id: str,
    api_version: str = Query("2023-07-31", alias="api-version"),
):
    try:
        parsed_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid Job ID format: {job_id}")

    from app.repositories.job_repository import job_repository
    job = job_repository.find_by_id(parsed_uuid)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    if job.status.to_friendly_string() == "running":
        return response_factory.create_polling_response(job)
    
    elif job.status.to_friendly_string() == "failed":
        return response_factory.create_error_response(job)

    else:
        logger.info(f"Job {job.job_id}: is completed")
        analyze_result_obj = azure_result_gen.generate_analyze_result(job, api_version=api_version)
        analyze_result_dict = azure_result_gen.to_dict(analyze_result_obj)
        return response_factory.create_success_response(analyze_result_dict)


@app.get("/documentintelligence/documentModels/{model_id}/analyzeResults/{job_id}/pdf", summary="Download of the processed PDF file")
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

    from app.repositories.job_repository import job_repository
    job = job_repository.find_by_id(parsed_uuid)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")
    
    pdf_bytes = job.final_pdf_bytes

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
