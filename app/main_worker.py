import base64
import io
import json
import logging
import sys
from typing import Any, Dict

import pika
from PIL import Image, ImageDraw, ImageFont

from ocr_engine.app.domain.commands import COMMAND_REGISTRY
from ocr_engine.app.services.config import logging, settings
from ocr_engine.app.services.job_command_publisher import command_publisher

logger = logging.getLogger(__name__)


def generate_test_image_base64(text: str) -> str:
    """Generiert zur Laufzeit ein valides PNG-Bild als Base64."""
    text = "Das ist ein Text"
    padding = 5

    # 1. Standard-Schriftart laden
    font = ImageFont.load_default()

    # 2. Textgröße berechnen
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 3. Canvas mit exakt 5px Padding erstellen
    img_width = int(text_w + (padding * 2))
    img_height = int(text_h + (padding * 2))

    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((padding - bbox[0], padding - bbox[1]), text, fill=(0, 0, 0), font=font)

    # 4. Als PNG zu Base64 konvertieren
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class WorkerService:

    def run_ocr_startup_self_test(self) -> bool:
        """Führt eine Test-Inferenz direkt an Ollama aus, um die Qualität zu prüfen."""
        logger.info("Starte OCR-Self-Test vor Worker-Loop...")

        EXPECTED_TEXT = "Das ist ein Text"

        try:
            from app.services.qwen25_vl import Qwen25VlQuery

            test_image_base64 = generate_test_image_base64(EXPECTED_TEXT)
            picture_bytes = base64.b64decode(test_image_base64)
            ocr_service = Qwen25VlQuery()
            response_text = ocr_service.process_page_with_boxes(picture_bytes)
            # 1. Prüfen ob response_text eine Länge größer 0 hat
            if not response_text or len(response_text.strip()) == 0:
                logger.error("Self-Test FEHLGESCHLAGEN: Inferenz lieferte leeren Response.")
                return False

            # 2. JSON-Parsing
            try:
                data = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"Self-Test FEHLGESCHLAGEN: Antwort ist kein JSON ({e}). Content: '{response_text}'")
                return False

            # 3. Prüfen ob data eine äußere Liste ist mit genau 1 Unterliste
            if not isinstance(data, list) or len(data) != 1:
                logger.error(f"Self-Test FEHLGESCHLAGEN: Erwartet genau 1 Element im Wurzel-Array, erhalten: {data}")
                return False

            first_item = data[0]

            # 4. Prüfen ob das innere Element eine Liste mit mindestens 6 Werten ist
            if not isinstance(first_item, list) or len(first_item) < 6:
                logger.error(f"Self-Test FEHLGESCHLAGEN: Element ist keine Liste mit 6 Werten: {first_item}")
                return False

            # Werte entpacken
            page, ymin, xmin, ymax, xmax, extracted_text = first_item[:6]

            # 5. Text-Vergleich (Case-Sensitive)
            if extracted_text != EXPECTED_TEXT:
                logger.error(
                    f"Self-Test FEHLGESCHLAGEN: Textabweichung. "
                    f"Erwartet: '{EXPECTED_TEXT}', Erhalten: '{extracted_text}'"
                )
                return False

            # 6. Bounding-Box Geometrie prüfen
            if not (ymin < ymax and xmin < xmax):
                logger.error(
                    f"Self-Test FEHLGESCHLAGEN: Bounding-Box Geometrie unlogisch: [{ymin}, {xmin}, {ymax}, {xmax}]"
                )
                return False

            logger.info("OCR-Self-Test ERFOLGREICH. Modell antwortet korrekt.")
            return True

        except Exception as e:
            logger.error(f"Self-Test FEHLGESCHLAGEN: Ausnahme aufgetreten: {e}")
            return False

    def _on_message(self, ch, method, properties, body):
        headers: Dict[str, Any] = properties.headers or {}
        command_type = headers.get("command_type")

        # Early Return + Type-Guard für Pylance (command_type ist ab hier garantiert str)
        if not command_type or not isinstance(command_type, str):
            logger.error(f"Ungültiger oder fehlender 'command_type'-Header: {command_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        command_cls = COMMAND_REGISTRY.get(command_type)
        if not command_cls:
            logger.error(f"Unbekannter Command-Typ: {command_type}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        # 1. Sofortiges ACK, um Heartbeat-Timeouts bei langen Inferenz-Aufrufen zu verhindern
        ch.basic_ack(delivery_tag=method.delivery_tag)

        try:
            raw_data = json.loads(body)

            # 2. Command-Instanz wiederherstellen
            command_instance = command_cls(**raw_data)

            # 3. Command führt sich selbst aus
            logger.info(f"Starte Ausführung für [{command_type}] (Job: {command_instance})")
            command_instance.execute()
            logger.info(f"Erfolgreich abgeschlossen: [{command_type}] (Job: {command_instance})")

        except Exception as e:
            logger.error(f"Fehler bei Execution von {command_type}: {e}", exc_info=True)

            # 4. Retry-Count erhöhen & Command erneut publizieren
            try:
                raw_data = json.loads(body)
                command_instance = command_cls(**raw_data)

                if hasattr(command_instance, "retry_count"):
                    command_instance.retry_count += 1

                logger.warning(
                    f"Reiher Task [{command_type}] für Job {command_instance} mit Retry-Count "
                    f"{getattr(command_instance, 'retry_count', 0)} erneut in die Queue ein."
                )
                command_publisher.publish_command(command_instance)
            except Exception as republish_error:
                logger.error(
                    f"Konnte fehlgeschlagenen Task [{command_type}] nicht re-publizieren: {republish_error}",
                    exc_info=True,
                )

    def start_listening(self):
        # 1. Startup-Self-Test durchführen
        if not self.run_ocr_startup_self_test():
            logger.critical("Worker wird aufgrund eines fehlerhaften OCR-Self-Tests NICHT gestartet.")
            sys.exit(1)  # Bricht den Container/Prozess ab (Docker startet ihn ggf. neu)

        # 2. Wenn Test OK -> Verbindung zu RabbitMQ herstellen
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

        logger.info("Worker erfolgreich gestartet. Warte auf Commands...")
        channel.start_consuming()


worker_service = WorkerService()


if __name__ == "__main__":
    worker_service.start_listening()
