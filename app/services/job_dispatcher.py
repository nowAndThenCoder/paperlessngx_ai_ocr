import logging
from app.services.job_command_publisher import command_publisher

logger = logging.getLogger(__name__)

class JobDispatcher:
    """
    Service that handles the dispatching of OCR jobs by publishing
    the initial command to the queue.
    """

    def dispatch_job(self, command) -> None:
        """
        Sends the initial command to the RabbitMQ queue.
        """
        try:
            command_publisher.publish_command(command)
            logger.info(f"Successfully dispatched job {command.job_id}")
        except Exception as e:
            logger.error(f"Failed to dispatch job {command.job_id}: {e}")
            raise

# Singleton instance
job_dispatcher = JobDispatcher()
