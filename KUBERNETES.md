# Kubernetes Deployment Guide

This guide will help you deploy the Natural Language SQL Interface to a Kubernetes cluster.

## 📋 Prerequisites

- Kubernetes cluster (local or cloud)
- `kubectl` configured to access your cluster
- Docker installed (for building images)
- Docker Hub account (or other container registry)

## 🚀 Quick Deployment

### 1. Update Configuration

Edit `k8s/01-secret.yaml` and update:
- Database connection details
- Gemini API key
- Application secret key

### 2. Build and Deploy

```bash
# Make the script executable
chmod +x build-and-deploy.sh

# Run the deployment script
./build-and-deploy.sh
```

## 📝 Manual Deployment Steps

### 1. Build Docker Image

```bash
# Build the image
docker build -t chandan1819/chat-with-database:latest .

# Push to registry
docker push chandan1819/chat-with-database:latest
```

### 2. Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/

# Or apply individually
kubectl apply -f k8s/01-secret.yaml
kubectl apply -f k8s/02-deployment.yaml
kubectl apply -f k8s/03-service.yaml
kubectl apply -f k8s/04-ingress.yaml
kubectl apply -f k8s/05-hpa.yaml
```

### 3. Optional: Deploy PostgreSQL

```bash
kubectl apply -f k8s/06-postgres.yaml
```

## 🔧 Configuration

### Environment Variables

The application supports these environment variables:

- `FLASK_HOST`: Host to bind to (default: 0.0.0.0)
- `FLASK_PORT`: Port to run on (default: 5000)
- `FLASK_ENV`: Environment (production/development)
- `FLASK_DEBUG`: Enable debug mode (true/false)

### Secrets

Update `k8s/01-secret.yaml` with your actual values:

```yaml
stringData:
  config.yaml: |
    database:
      host: your-postgres-host
      username: your-db-user
      password: your-db-password
      database: your-db-name
    gemini:
      api_key: your-gemini-api-key
```

## 📊 Monitoring

### Check Deployment Status

```bash
# Check pods
kubectl get pods -l app=nl2sql-app

# Check services
kubectl get services

# Check ingress
kubectl get ingress

# View logs
kubectl logs -l app=nl2sql-app -f
```

### Health Checks

The application includes health checks:
- **Liveness Probe**: `/health` endpoint
- **Readiness Probe**: `/health` endpoint

## 🔄 Scaling

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment nl2sql-app --replicas=5
```

### Auto Scaling

The HPA (HorizontalPodAutoscaler) automatically scales based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)
- Min replicas: 2
- Max replicas: 10

## 🌐 Accessing the Application

### Via Service (Internal)

```bash
# Port forward for local access
kubectl port-forward service/nl2sql-service 8080:80

# Access at http://localhost:8080
```

### Via Ingress (External)

Update `k8s/04-ingress.yaml` with your domain and deploy:

```bash
kubectl apply -f k8s/04-ingress.yaml
```

## 🗄️ Database Setup

### Using External Database

Update the database configuration in `k8s/01-secret.yaml` with your external PostgreSQL details.

### Using In-Cluster PostgreSQL

Deploy the included PostgreSQL:

```bash
kubectl apply -f k8s/06-postgres.yaml
```

Then create test tables:

```bash
# Connect to PostgreSQL pod
kubectl exec -it deployment/postgres -- psql -U nl2sql_user -d nl2sql_db

# Run the setup script
\i /path/to/setup_test_db.sql
```

## 🔐 Security Considerations

- **Secrets**: All sensitive data is stored in Kubernetes secrets
- **Non-root user**: Container runs as non-root user (UID 1000)
- **Resource limits**: CPU and memory limits are set
- **Network policies**: Consider implementing network policies for additional security

## 🛠️ Troubleshooting

### Common Issues

1. **Image Pull Errors**
   ```bash
   # Check if image exists
   docker pull chandan1819/chat-with-database:latest
   ```

2. **Configuration Issues**
   ```bash
   # Check secret
   kubectl describe secret nl2sql-config
   
   # Check pod logs
   kubectl logs -l app=nl2sql-app
   ```

3. **Database Connection Issues**
   ```bash
   # Test database connectivity
   kubectl exec -it deployment/nl2sql-app -- python -c "
   from nl2sql.config.manager import Config_Manager
   from nl2sql.database.connector import Database_Connector
   config = Config_Manager()
   config.load_config()
   db = Database_Connector(config.database_config)
   db.test_connection()
   print('Database connection successful!')
   "
   ```

### Useful Commands

```bash
# View all resources
kubectl get all -l app=nl2sql-app

# Describe deployment
kubectl describe deployment nl2sql-app

# Get events
kubectl get events --sort-by=.metadata.creationTimestamp

# Delete deployment
kubectl delete -f k8s/
```

## 📈 Production Considerations

1. **Resource Requests/Limits**: Adjust based on your workload
2. **Persistent Storage**: Use persistent volumes for database
3. **SSL/TLS**: Configure SSL certificates for ingress
4. **Monitoring**: Set up monitoring with Prometheus/Grafana
5. **Logging**: Configure centralized logging
6. **Backup**: Implement database backup strategy
7. **Security**: Implement network policies and pod security policies

## 🔄 Updates

To update the application:

```bash
# Build new image with version tag
docker build -t chandan1819/chat-with-database:v1.1.0 .
docker push chandan1819/chat-with-database:v1.1.0

# Update deployment
kubectl set image deployment/nl2sql-app nl2sql-app=chandan1819/chat-with-database:v1.1.0

# Check rollout status
kubectl rollout status deployment/nl2sql-app
```