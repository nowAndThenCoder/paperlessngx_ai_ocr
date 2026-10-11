import base64
import json
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.domain.models.job import FileType
from .config import logging, settings

logger = logging.getLogger(__name__)


class RestClient:
    def __init__(self):
        # create connection with connection pooling and automatic retries
        self.session = requests.Session()

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_file_bytes_from_request(self, content_type: str, body_bytes: bytes) -> bytes:
        """fetches the binary content from the request

        Args:
            content_type (str): _content type_
            body_bytes (bytes): _content of the body in bytes_

        Raises:
            ValueError: _when no bytes are received_
            ValueError: _when body is defined as json but actually is not_
            ValueError: _when body is defined as json but has no attributes 'base64Source' nor 'source'
            ValueError: _when source data are not decodable as base64_

        Returns:
            bytes: _bytes of the request_
        """
        if not body_bytes:
            raise ValueError("No bytes in the body received")

        if "application/json" not in content_type.lower():
            return body_bytes

        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error with treating body as json: {e}")
            raise ValueError(f"Error with treating body as json: {e}") from e

        # content is json and can be treated as such
        if "base64Source" in body_json:
            source_data = body_json["base64Source"]
        elif "source" in body_json:
            source_data = body_json["source"]
        else:
            raise ValueError("Error obtaining binary data via 'base64Source' nor 'source'")

        # binary data will be decoded now
        try:
            return base64.b64decode(source_data)
        except Exception as e:
            logger.error(f"Error decoding Base64-data: {e}")
            raise ValueError(f"Error decoding Base64-data: {e}") from e

    def get_file_type_of_bytes(self, binary_data: bytes) -> FileType:
        if binary_data.startswith(b"%PDF"):
            file_type = FileType.PDF
        elif binary_data.startswith(b"\x89PNG"):
            file_type = FileType.PNG
        elif binary_data.startswith(b"\xff\xd8\xff"):
            file_type = FileType.JPEG
        elif binary_data.startswith(b"II*\x00") or binary_data.startswith(b"MM\x00*"):
            file_type = FileType.TIFF
        elif binary_data.startswith(b"BM"):
            file_type = FileType.BMP
        elif binary_data.startswith(b"RIFF") and len(binary_data) >= 12 and binary_data[8:12] == b"WEBP":
            file_type = FileType.WEBP
        else:
            file_type = FileType.UNKNOWN

        return file_type


rest_client = RestClient()
