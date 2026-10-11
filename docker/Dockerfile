FROM python:3.14-slim

# System-Abhängigkeiten für C-Extensions (u. a. PyMuPDF/fitz & LanceDB-Unterbau)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements kopieren und ohne Caching installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY . .

# Port 5000 für die Paperless-Integration freigeben
EXPOSE 5000

# Startkommando via Uvicorn auf 0.0.0.0
CMD ["uvicorn", "app.main_restapi:app", "--host", "0.0.0.0", "--port", "5000"]
