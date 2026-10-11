import json
import logging
import pika
from app.domain.commands import BaseCommand
from app.services.config import settings

logger = logging.getLogger(__name__)

class JobCommandPublisher:
    """
    Service responsible for publishing OCR commands to the RabbitMQ queue.
    """

    def __init__(self):
        self.queue_name = "ocr_commands"
        self._connection = None
        self._channel = None

    def _ensure_connection(self):
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=settings.RABBITMQ_HOST)
                )
                self._channel = self._connection.channel()
                self._channel.queue_declare(queue=self.queue_name, durable=True)
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise

    def publish_command(self, command: BaseCommand) -> None:
        """
        Serializes a command and publishes it to the RabbitMQ queue.
        """
        try:
            self._ensure_connection()
            
            # Serialize the Pydantic model to JSON
            payload = command.model_dump_json()
            
            self._channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=payload,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            logger.debug(f"Published command {command.__class__.__name__} for job {command.job_id}")
        except Exception as e:
            logger.error(f"Failed to publish command {command.__class__.__name__} for job {command.job_id}: {e}")
            raise

# Singleton instance
command_publisher = JobCommandPublisher()
