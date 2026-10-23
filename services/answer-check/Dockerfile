# Answer-check service (grading API). Build from the repository root:
#   docker build -f services/answer-check/Dockerfile -t answer-check .
# PyTorch is deliberately not installed: the vision reader does the reading and the handwriting
# fallback is optional. This keeps the image and memory use small enough for a free host.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/answer-check/requirements.txt /app/services/answer-check/requirements.txt
RUN pip install -r /app/services/answer-check/requirements.txt

# The service reads the paper data, the model adapters and its own cache from the repository layout.
COPY packages/model-adapters /app/packages/model-adapters
COPY apps/web/src/data/import-preview-report.json /app/apps/web/src/data/import-preview-report.json
COPY services/answer-check /app/services/answer-check

WORKDIR /app/services/answer-check
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8001}"]
