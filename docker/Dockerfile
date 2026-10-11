FROM python:3.14-slim

# System dependencies for C-Extensions (e.g. PyMuPDF & LanceDB base)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install without caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 5000 for Paperless integration
EXPOSE 5000

# Start command via Uvicorn on 0.0.0.0
CMD ["uvicorn", "app.main_restapi:app", "--host", "0.0.0.0", "--port", "5000"]
