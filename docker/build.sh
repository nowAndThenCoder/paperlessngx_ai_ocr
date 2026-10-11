#!/bin/bash

# Configuration
REGISTRY="dockerregistry.home.local"
IMAGE_NAME="azure-ocr-wrapper"
TAG="0.1.0"

FULL_IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:latest"

echo -e "\e[32m1. Building Docker Image...\e[0m"
docker build -f Dockerfile -t "$FULL_IMAGE_TAG" -t "$LATEST_IMAGE_TAG" ..

if [ $? -ne 0 ]; then
    echo -e "\e[31mDocker Build failed!\e[0m"
    exit 1
fi

echo -e "\e[32m2. Pushing Image to Registry...\e[0m"
docker push "$FULL_IMAGE_TAG"
docker push "$LATEST_IMAGE_TAG"

echo -e "\e[36mSuccessfully pushed to Registry: $FULL_IMAGE_TAG\e[0m"
