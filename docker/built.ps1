# Konfiguration deiner Registry
$REGISTRY = "registry.deine-domain.de"  # oder IP:Port (z. B. 192.168.1.50:5000)
$IMAGE_NAME = "ocr-engine"
$TAG = "v2.0"

$FULL_IMAGE_TAG = "${REGISTRY}/${IMAGE_NAME}:${TAG}"
$LATEST_IMAGE_TAG = "${REGISTRY}/${IMAGE_NAME}:latest"

Write-Host "1. Baue Docker Image..." -ForegroundColor Green
docker build -f Dockerfile -t $FULL_IMAGE_TAG -t $LATEST_IMAGE_TAG ..

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Build fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

Write-Host "2. PUSHE Image in die Registry..." -ForegroundColor Green
docker push $FULL_IMAGE_TAG
docker push $LATEST_IMAGE_TAG

Write-Host "Erfolgreich in Registry gepusht: $FULL_IMAGE_TAG" -ForegroundColor Cyan



#docker build -t dockerregistry.home.local/azure-ocr-wrapper:v1.0.0 .
#docker push dockerregistry.home.local/azure-ocr-wrapper:v1.0.0