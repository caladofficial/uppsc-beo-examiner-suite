# Answer-check service. Build from the repository root:
#   docker build -f services/answer-check/Dockerfile -t answer-check .
# The service reads the model adapters, the paper data and its own cache from the repository layout,
# so the image keeps the same folders.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/answer-check/requirements.txt /app/services/answer-check/requirements.txt
RUN pip install -r /app/services/answer-check/requirements.txt \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY packages/model-adapters /app/packages/model-adapters
COPY apps/web/src/data/import-preview-report.json /app/apps/web/src/data/import-preview-report.json
COPY services/answer-check /app/services/answer-check

WORKDIR /app/services/answer-check
EXPOSE 8001
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8001}"]
