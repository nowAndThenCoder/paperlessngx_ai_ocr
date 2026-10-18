from typing import Any, Dict, Optional
from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    DocumentPage,
    DocumentLine,
    DocumentWord,
)
from app.domain.models.job import Job
from app.domain.models.ocr import OcrDocument

class AzureAIResultGenerator:
    """
    Generates Azure AI Document Intelligence compatible responses.
    Using official Microsoft models to ensure SDK compatibility on the client side.
    """

    def __init__(self, api_version: str = "2023-07-31", model_id: str = "prebuilt-read"):
        self.api_version = api_version
        self.model_id = model_id

    def generate_analyze_result(self, job: Job, api_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Transforms a Job and its merged OCR results into an Azure AI compatible response dictionary.
        """
        # 1. Prepare the full content string (concatenated text of all pages)
        full_content = job.get_full_text()

        # 3. Return as a dictionary that mimics AnalyzeResult
        return {
            "apiVersion": api_version or self.api_version,
            "modelId": self.model_id,
            "stringIndexType": "textElements",
            "content": full_content,
            "pages": [],
            "paragraphs": [],
            "tables": [],
            "figures": [],
            "sections": [],
            "keyValuePairs": [],
            "styles": [],
            "languages": [],
            "documents": [],
            "warnings": []
        }

    def to_dict(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts the AnalyzeResult model to a dictionary for JSONResponse.
        Ensures that mandatory fields like 'content' are explicitly included.
        """
        data = self._recursive_to_primitive(result)
        
        return data

    def _recursive_to_primitive(self, obj: Any) -> Any:
        """
        Recursively converts an object (Pydantic model, dataclass, or plain class) 
        into a JSON-serializable primitive (dict, list, str, int, float, bool, None).
        """
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {str(k): self._recursive_to_primitive(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [self._recursive_to_primitive(i) for i in obj]
        
        # Handle Pydantic v2
        if hasattr(obj, "model_dump"):
            return self._recursive_to_primitive(obj.model_dump())
        # Handle Pydantic v1 / older models
        if hasattr(obj, "dict"):
            return self._recursive_to_primitive(obj.dict())
        # Handle plain classes / dataclasses
        if hasattr(obj, "__dict__"):
            return self._recursive_to_primitive(vars(obj))
        
        return str(obj)
