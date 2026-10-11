$env:LOG_LEVEL="DEBUG"
$env:REDIS_HOST="localhost"
$env:REDIS_PORT=6379
$env:OLLAMA_URL="http://192.168.1.12:11434"
$env:OLLAMA_MODEL_VL="qwen2.5vl:7b"
$env:OLLAMA_MODEL_TEXTEMBED="nomic-embed-text"
$env:OLLAMA_TIMEOUT=4800
$env:OLLAMA_DPI=300
$env:LANCEDB_DATA_DIR="./lancedb_data"
$env:MAX_PARALLEL_JOBS=1
$env:MAX_THREADS_PER_JOB=1
$env:PYTHONUNBUFFERED=1
$env:RABBITMQ_HOST="localhost"

# -m uvicorn startet den REST-API-Server mit Hot-Reloading für Entwicklungszwecke
python -m uvicorn app.main_restapi:app --host 0.0.0.0 --port 5000 --reload --log-level debug