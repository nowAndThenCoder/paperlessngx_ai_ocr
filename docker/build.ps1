

# Registry configuration
$REGISTRY = "dockerregistry.home.local"
$IMAGE_NAME = "azure-ocr-wrapper"
$TAG = "0.1.0"

$FULL_IMAGE_TAG = "${REGISTRY}/${IMAGE_NAME}:${TAG}"
$LATEST_IMAGE_TAG = "${REGISTRY}/${IMAGE_NAME}:latest"

Write-Host "1. Building Docker Image..." -ForegroundColor Green
docker build -f Dockerfile -t $FULL_IMAGE_TAG -t $LATEST_IMAGE_TAG ..

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "2. Pushing Image to Registry..." -ForegroundColor Green
docker push $FULL_IMAGE_TAG
docker push $LATEST_IMAGE_TAG

Write-Host "Successfully pushed to Registry: $FULL_IMAGE_TAG" -ForegroundColor Cyan
