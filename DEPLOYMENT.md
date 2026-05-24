# Deployment Guide

## Prerequisites

- Python 3.9+
- Ollama running locally
- Required Python packages

## Local Development

```bash
pip install -r requirements.txt
python -m llm_os
```

## Docker Deployment

```bash
docker build -t llm-os .
docker run -p 8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 llm-os
```

## Kubernetes

```bash
kubectl apply -f k8s/
```
