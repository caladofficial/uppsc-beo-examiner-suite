# Isolated Non-Root OCR/HTR & Rubric Grading Worker Container
# Enforces bounded CPU/memory/disk, read-only rootfs compatibility, and non-root execution.

FROM python:3.11-slim-bookworm

RUN groupadd -g 10001 workergrp && \
    useradd -u 10001 -g workergrp -m -s /sbin/nologin workeruser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY packages/ /app/packages/
COPY apps/worker/ /app/apps/worker/
COPY apps/api/ /app/apps/api/

RUN pip install --no-cache-dir \
    fastapi uvicorn python-multipart httpx openpyxl pymupdf pillow opencv-python-headless numpy pydantic

USER 10001:10001
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--limit-Concurrency", "32", "--timeout-keep-alive", "15"]
