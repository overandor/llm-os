# VM LLM OS Online — Container image
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY llm_os/ ./llm_os/

# Install package in editable mode so imports resolve
RUN pip install -e .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV MEMBRA_MODE=simulation

CMD ["python", "-m", "llm_os", "serve", "--host", "0.0.0.0", "--port", "8080"]
