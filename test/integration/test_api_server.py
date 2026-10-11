import pytest
import httpx
import asyncio
from fastapi import FastAPI
from app.main_restapi import app as api_app
from app.services.config import settings
import uvicorn
from multiprocessing import Process
import time

# Configuration for the test server
HOST = "127.0.0.1"
PORT = 5005  # Use a different port for tests to avoid collisions

def run_server():
    """Function to run the FastAPI server in a separate process."""
    uvicorn.run(api_app, host=HOST, port=PORT, log_level="error")

@pytest.fixture(scope="module")
def server():
    """
    Starts the API server in a background process.
    Yields a base URL for the client to use.
    """
    process = Process(target=run_server)
    process.start()
    
    # Give the server a moment to start up
    time.sleep(2)
    
    yield f"http://{HOST}:{PORT}"
    
    process.terminate()
    process.join()

@pytest.mark.asyncio
async def test_api_server_starts_and_responds(server):
    """
    Verify that the API server starts successfully and 
    responds to a basic request (e.g., the root or docs).
    """
    async with httpx.AsyncClient(base_url=server) as client:
        # We check the /docs endpoint as it is defined in the app
        response = await client.get("/docs")
        
        # Assert that the server is up and returning a successful response
        assert response.status_code == 200
        assert "FastAPI" in response.text

@pytest.mark.asyncio
async def test_analyze_endpoint_exists(server):
    """
    Verify that the analyze endpoint is accessible and 
    returns a 405 if called with GET (should be POST).
    """
    async with httpx.AsyncClient(base_url=server) as client:
        # The analyze endpoint: /documentintelligence/documentModels/{model_id}:analyze
        # Using a dummy model_id
        url = "/documentintelligence/documentModels/prebuilt-read:analyze"
        response = await client.get(url)
        
        # It should return 405 Method Not Allowed because it expects POST
        assert response.status_code == 405
