import pytest
import redis
import pika
from app.services.config import settings

def test_redis_connection():
    """
    Verify that the application can connect to the configured Redis instance.
    """
    try:
        # Create a redis client using the configured URL
        client = redis.from_url(settings.redis_url, socket_timeout=5)
        # Send a PING command to check if the server is alive
        response = client.ping()
        assert response is True, "Redis PING failed"
    except redis.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}. Error: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while testing Redis connection: {e}")

def test_rabbitmq_connection():
    """
    Verify that the application can connect to the configured RabbitMQ broker.
    """
    try:
        # Connection parameters based on current settings
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=5672, # Default RabbitMQ port
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=5
        )
        # Attempt to establish a connection
        connection = pika.BlockingConnection(parameters)
        
        # If we reach here, connection was successful
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        pytest.fail(f"Could not connect to RabbitMQ at {settings.RABBITMQ_HOST}. Error: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while testing RabbitMQ connection: {e}")
