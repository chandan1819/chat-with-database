#!/bin/bash

# Build and Deploy Script for Natural Language SQL Interface
set -e

# Configuration
IMAGE_NAME="chandan1819/chat-with-database"
IMAGE_TAG="latest"
NAMESPACE="default"

echo "🐳 Building Docker image..."

# Build Docker image
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "✅ Docker image built successfully!"

# Push to registry (uncomment if using Docker Hub or other registry)
echo "📤 Pushing image to registry..."
docker push ${IMAGE_NAME}:${IMAGE_TAG}

echo "✅ Image pushed successfully!"

echo "🚀 Deploying to Kubernetes..."

# Apply Kubernetes manifests
kubectl apply -f k8s/01-secret.yaml
kubectl apply -f k8s/02-deployment.yaml
kubectl apply -f k8s/03-service.yaml
kubectl apply -f k8s/04-ingress.yaml
kubectl apply -f k8s/05-hpa.yaml

# Optional: Deploy PostgreSQL (uncomment if needed)
# kubectl apply -f k8s/06-postgres.yaml

echo "✅ Deployment completed!"

echo "📊 Checking deployment status..."
kubectl get pods -l app=nl2sql-app
kubectl get services nl2sql-service
kubectl get ingress nl2sql-ingress

echo "🎉 Deployment successful! Your application should be available soon."
echo "💡 To check logs: kubectl logs -l app=nl2sql-app -f"
echo "💡 To check status: kubectl get pods -l app=nl2sql-app"