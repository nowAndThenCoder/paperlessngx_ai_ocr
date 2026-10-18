import logging
import pika
from typing import Optional
from app.domain.commands import BaseCommand
from app.services.config import settings

logger = logging.getLogger(__name__)

class JobCommandPublisher:
    """
    Service responsible for publishing OCR commands to the RabbitMQ queue.
    """

    def __init__(self):
        self.queue_name = settings.RABBITMQ_QUEUE_NAME
        self._connection = None
        self._channel = None

    def _ensure_connection(self):
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=settings.RABBITMQ_HOST,
                        heartbeat=60 # Keep connection alive
                    )
                )
                self._channel = self._connection.channel()
                self._channel.queue_declare(queue=self.queue_name, durable=True)
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise

    def _close_connection(self):
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception:
            pass
        finally:
            self._connection = None
            self._channel = None

    def publish_command(self, command: BaseCommand, queue_name: Optional[str] = None) -> None:
        try:
            self._do_publish(command, queue_name)
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            logger.warning(f"Connection lost. Retrying publish for job {command.job_id}... Error: {e}")
            self._close_connection()
            self._do_publish(command, queue_name)
        except Exception as e:
            logger.error(f"Permanent failure publishing command {command.__class__.__name__} for job {command.job_id}: {e}")
            raise

    def _do_publish(self, command: BaseCommand, queue_name: Optional[str]) -> None:
        self._ensure_connection()
        target_queue = queue_name or settings.RABBITMQ_QUEUE_NAME
        payload = command.model_dump_json()
        self._channel.basic_publish(
            exchange='',
            routing_key=target_queue,
            body=payload,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={'command_type': command.__class__.__name__},
            )
        )
        logger.debug(f"Published command {command.__class__.__name__} for job {command.job_id} to {target_queue}")

# Singleton instance
command_publisher = JobCommandPublisher()
