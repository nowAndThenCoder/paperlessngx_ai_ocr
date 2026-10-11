#!/bin/bash
# Build and Push Docker Image to Registry

# Configuration
REGISTRY="registry.deine-domain.de" # or IP:Port (e.g., 192.168.1.50:5000)
IMAGE_NAME="ocr-engine"
TAG="v2.0"

FULL_IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:latest"

echo -e "\e[32m1. Building Docker Image...\e[0m"
# We use -f Dockerfile and point the build context to the parent directory (..)
docker build -f Dockerfile -t "$FULL_IMAGE_TAG" -t "$LATEST_IMAGE_TAG" ..

if [ $? -ne 0 ]; then
    echo -e "\e[31mDocker Build failed!\e[0m"
    exit 1
fi

echo -e "\e[32m2. Pushing Image to Registry...\e[0m"
docker push "$FULL_IMAGE_TAG"
docker push "$LATEST_IMAGE_TAG"

echo -e "\e[36mSuccessfully pushed to Registry: $FULL_IMAGE_TAG\e[0m"
