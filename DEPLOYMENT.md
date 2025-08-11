# 🚀 PR Agentic Workflow - Deployment Guide

This guide covers all deployment options for the PR Agentic Workflow agent.

## 🎯 Deployment Options

### 1. Docker Deployment (Recommended)

#### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

#### Quick Deployment
```bash
# Clone the repository
git clone <your-repo-url>
cd PR-agentic-workflow

# Configure environment variables
export GITHUB_TOKEN="your_github_token"
export PERPLEXITY_API_KEY="your_perplexity_key"

# Deploy
./deploy.sh
```

#### Manual Docker Deployment
```bash
# Build the image
docker build -t pr-agentic-workflow .

# Run the container
docker run -d \
  --name pr-agentic-workflow \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/logs:/app/logs \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e PERPLEXITY_API_KEY=$PERPLEXITY_API_KEY \
  pr-agentic-workflow
```

### 2. Cloud-Native Deployment

#### GitHub Actions (Free for public repos)
```yaml
# .github/workflows/pr-agent.yml
name: PR Agent Workflow
on:
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:

jobs:
  pr-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run PR Agent
        run: python run_agent.py --review --pr ${{ github.event.pull_request.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
```

#### AWS ECS/Fargate
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker build -t pr-agentic-workflow .
docker tag pr-agentic-workflow:latest $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/pr-agentic-workflow:latest
docker push $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/pr-agentic-workflow:latest

# Deploy to ECS
aws ecs create-service \
  --cluster your-cluster \
  --service-name pr-agentic-workflow \
  --task-definition pr-agentic-workflow:1 \
  --desired-count 1
```

#### Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT/pr-agentic-workflow
gcloud run deploy pr-agentic-workflow \
  --image gcr.io/YOUR_PROJECT/pr-agentic-workflow \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 3. Self-Hosted Deployment

#### VPS Deployment (DigitalOcean, Linode, Vultr)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Deploy
git clone <your-repo-url>
cd PR-agentic-workflow
./deploy.sh
```

#### Kubernetes Deployment
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pr-agentic-workflow
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pr-agentic-workflow
  template:
    metadata:
      labels:
        app: pr-agentic-workflow
    spec:
      containers:
      - name: pr-agentic-workflow
        image: pr-agentic-workflow:latest
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: github-secret
              key: token
        - name: PERPLEXITY_API_KEY
          valueFrom:
            secretKeyRef:
              name: perplexity-secret
              key: api-key
        volumeMounts:
        - name: config
          mountPath: /app/config.toml
          subPath: config.toml
        - name: workspace
          mountPath: /app/workspace
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: config
        configMap:
          name: pr-agent-config
      - name: workspace
        emptyDir: {}
      - name: logs
        emptyDir: {}
```

## 🔧 Configuration

### Environment Variables
```bash
# Required
GITHUB_TOKEN=your_github_token
PERPLEXITY_API_KEY=your_perplexity_key

# Optional
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### Configuration File
```toml
# config.toml
[github]
repo_owner = "your-username"
repo_name = "your-repo"
token = "your-github-token"

[llm]
provider = "perplexity"
api_key = "your-perplexity-key"

[notification]
email_enabled = true
slack_enabled = false
```

## 📊 Monitoring and Logging

### Health Checks
```bash
# Check container health
docker ps
docker-compose ps

# View logs
docker-compose logs -f pr-agent
docker logs pr-agentic-workflow
```

### Metrics
```bash
# Resource usage
docker stats pr-agentic-workflow

# Log analysis
docker-compose logs pr-agent | grep ERROR
```

## 🔄 Updates and Maintenance

### Updating the Agent
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Backup and Recovery
```bash
# Backup configuration
cp config.toml config.toml.backup

# Backup workspace
tar -czf workspace-backup.tar.gz workspace/

# Restore
cp config.toml.backup config.toml
tar -xzf workspace-backup.tar.gz
```

## 🛠️ Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   docker-compose logs pr-agent
   
   # Check configuration
   docker-compose config
   ```

2. **Permission issues**
   ```bash
   # Fix permissions
   sudo chown -R $USER:$USER workspace/ logs/
   ```

3. **Network issues**
   ```bash
   # Check network connectivity
   docker network ls
   docker network inspect pr-agentic-workflow_pr-agent-network
   ```

### Performance Optimization

1. **Resource limits**
   ```yaml
   # docker-compose.yml
   services:
     pr-agent:
       deploy:
         resources:
           limits:
             memory: 1G
             cpus: '0.5'
   ```

2. **Caching**
   ```dockerfile
   # Dockerfile
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   ```

## 🔒 Security Considerations

1. **Secrets Management**
   - Use environment variables for sensitive data
   - Consider using Docker secrets or Kubernetes secrets
   - Never commit secrets to version control

2. **Network Security**
   - Use internal networks for inter-service communication
   - Limit external access to necessary ports only
   - Consider using VPN for secure access

3. **Container Security**
   - Run containers as non-root users
   - Regularly update base images
   - Scan images for vulnerabilities

## 📈 Scaling

### Horizontal Scaling
```bash
# Scale to multiple instances
docker-compose up -d --scale pr-agent=3
```

### Load Balancing
```yaml
# nginx.conf
upstream pr_agents {
    server pr-agentic-workflow:8000;
    server pr-agentic-workflow:8001;
    server pr-agentic-workflow:8002;
}
```

## 🎯 Best Practices

1. **Use specific image tags** instead of `latest`
2. **Implement health checks** for all services
3. **Use resource limits** to prevent resource exhaustion
4. **Implement proper logging** and monitoring
5. **Regular backups** of configuration and data
6. **Test deployments** in staging environment first
7. **Document changes** and maintain deployment runbooks

## 📞 Support

For deployment issues:
- Check the troubleshooting section
- Review logs and error messages
- Consult the main README.md
- Open an issue on GitHub
