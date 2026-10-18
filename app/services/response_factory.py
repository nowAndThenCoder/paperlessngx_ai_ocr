from typing import Any, Dict
from fastapi.responses import JSONResponse
from app.domain.models.job import Job

class ResponseFactory:
    """
    Factory to generate standardized responses compatible with the 
    Azure AI Document Intelligence API specification.
    """

    @staticmethod
    def create_polling_response(job: Job) -> JSONResponse:
        """
        Creates a response for jobs that are still in progress.
        """
        return JSONResponse(
            status_code=200,
            content={
                "status": job.status.to_friendly_string(),
                "percentCompleted": 0,
            },
        )

    @staticmethod
    def create_error_response(job: Job) -> JSONResponse:
        """
        Creates a response for jobs that have failed.
        """
        return JSONResponse(
            status_code=200,
            content={
                "status": "failed",
                "error": {
                    "code": "InternalServerError",
                    "message": getattr(job, "error_message", None) or "Unknown error during OCR processing.",
                },
            },
        )

    @staticmethod
    def create_success_response(analyze_result_dict: Dict[str, Any]) -> JSONResponse:
        """
        Creates a response for successfully completed jobs.
        Wraps the result in a top-level object containing the status, as required by the Azure SDK.
        """
        return JSONResponse(
            status_code=200,
            content={
                "status": "succeeded",
                "analyzeResult": analyze_result_dict,
            },
        )

# Singleton instance
response_factory = ResponseFactory()
