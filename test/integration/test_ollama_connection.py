import pytest
from app.services.ollama_client import ollama_client

def test_ollama_connection():
    """
    Verify that the application can reach the Ollama server.
    """
    try:
        is_alive = ollama_client.check_health()
        assert is_alive is True, "Ollama server is not reachable at the configured URL"
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while testing Ollama connection: {e}")
