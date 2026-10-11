import base64
import io
import json
import logging
import sys
from typing import Any, Dict

import pika
from PIL import Image, ImageDraw, ImageFont

from app.domain.commands import COMMAND_REGISTRY
from app.services.config import logging, settings
from app.services.job_command_publisher import command_publisher

logger = logging.getLogger(__name__)


def generate_test_image_base64(text: str) -> str:
    """Generates a valid PNG image as Base64 at runtime."""
    text = "Das ist ein Text"
    padding = 5

    # 1. Load default font
    font = ImageFont.load_default()

    # 2. Calculate text size
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 3. Create canvas with exactly 5px padding
    img_width = int(text_w + (padding * 2))
    img_height = int(text_h + (padding * 2))

    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((padding - bbox[0], padding - bbox[1]), text, fill=(0, 0, 0), font=font)

    # 4. Convert to PNG and then to Base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class WorkerService:

    def run_ocr_startup_self_test(self) -> bool:
        """Performs a test inference directly on Ollama to verify quality."""
        logger.info("Starting OCR self-test before worker loop...")

        EXPECTED_TEXT = "Das ist ein Text"

        try:
            from app.services.ocr_query_service import OcrQueryService

            test_image_base64 = generate_test_image_base64(EXPECTED_TEXT)
            picture_bytes = base64.b64decode(test_image_base64)
            ocr_service = OcrQueryService()
            response_text = ocr_service.process_page_with_boxes(picture_bytes)
            # 1. Check if response_text has length > 0
            if not response_text or len(response_text.strip()) == 0:
                logger.error("Self-Test FAILED: Inference returned empty response.")
                return False

            # 2. JSON-Parsing
            try:
                data = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"Self-Test FAILED: Response is not JSON ({e}). Content: '{response_text}'")
                return False

            # 3. Check if data is an outer list with exactly 1 inner list
            if not isinstance(data, list) or len(data) != 1:
                logger.error(f"Self-Test FAILED: Expected exactly 1 element in root array, received: {data}")
                return False

            first_item = data[0]

            # 4. Check if the inner element is a list with at least 6 values
            if not isinstance(first_item, list) or len(first_item) < 6:
                logger.error(f"Self-Test FAILED: Element is not a list with 6 values: {first_item}")
                return False

            # Unpack values
            page, ymin, xmin, ymax, xmax, extracted_text = first_item[:6]

            # 5. Text comparison (Case-Sensitive)
            if extracted_text != EXPECTED_TEXT:
                logger.error(
                    f"Self-Test FAILED: Text mismatch. "
                    f"Expected: '{EXPECTED_TEXT}', Received: '{extracted_text}'"
                )
                return False

            # 6. Verify bounding box geometry
            if not (ymin < ymax and xmin < xmax):
                logger.error(
                    f"Self-Test FAILED: Bounding box geometry is illogical: [{ymin}, {xmin}, {ymax}, {xmax}]"
                )
                return False

            logger.info("OCR Self-Test SUCCESSFUL. Model is responding correctly.")
            return True

        except Exception as e:
            logger.error(f"Self-Test FAILED: Exception occurred: {e}")
            return False

    def _on_message(self, ch, method, properties, body):
        headers: Dict[str, Any] = properties.headers or {}
        command_type = headers.get("command_type")

        # Early Return + Type-Guard for Pylance (command_type is guaranteed to be str from here)
        if not command_type or not isinstance(command_type, str):
            logger.error(f"Invalid or missing 'command_type' header: {command_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        command_cls = COMMAND_REGISTRY.get(command_type)
        if not command_cls:
            logger.error(f"Unknown command type: {command_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        # 1. Immediate ACK to prevent heartbeat timeouts during long inference calls
        ch.basic_ack(delivery_tag=method.delivery_tag)

        try:
            raw_data = json.loads(body)

            # 2. Restore command instance
            command_instance = command_cls(**raw_data)

            # 3. Command executes itself
            logger.info(f"Starting execution for [{command_type}] (Job: {command_instance})")
            command_instance.execute()
            logger.info(f"Successfully completed: [{command_type}] (Job: {command_instance})")

        except Exception as e:
            logger.error(f"Error during execution of {command_type}: {e}", exc_info=True)

            # 4. Increase retry count & republish command
            try:
                raw_data = json.loads(body)
                command_instance = command_cls(**raw_data)

                if hasattr(command_instance, "retry_count"):
                    command_instance.retry_count += 1

                logger.warning(
                    f"Re-queueing Task [{command_type}] for Job {command_instance} with retry count "
                    f"{getattr(command_instance, 'retry_count', 0)}."
                )
                command_publisher.publish_command(command_instance)
            except Exception as republish_error:
                logger.error(
                    f"Could not republish failed task [{command_type}]: {republish_error}",
                    exc_info=True,
                )

    def start_listening(self):
        # 1. Perform startup self-test
        if not self.run_ocr_startup_self_test():
            logger.critical("Worker NOT starting due to failed OCR self-test.")
            sys.exit(1)  # Terminates the container/process (Docker may restart it)

        # 2. If test OK -> establish connection to RabbitMQ
        heartbeat_timeout = getattr(settings, "OLLAMA_TIMEOUT", 300) + 60
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            heartbeat=heartbeat_timeout,
            blocked_connection_timeout=300,
        )

        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue="ocr_job_tasks", durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue="ocr_job_tasks", on_message_callback=self._on_message)

        logger.info("Worker started successfully. Waiting for commands...")
        channel.start_consuming()


worker_service = WorkerService()


if __name__ == "__main__":
    worker_service.start_listening()
