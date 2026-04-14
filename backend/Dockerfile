FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        tesseract-ocr-mar \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.docker.txt .
COPY requirements.paddle.txt .

# Set INSTALL_PADDLE_OCR=1 at build time to include PaddleOCR deps.
ARG INSTALL_PADDLE_OCR=0

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.docker.txt \
    && if [ "$INSTALL_PADDLE_OCR" = "1" ]; then pip install --no-cache-dir -r requirements.paddle.txt; fi \
    && pip install --no-cache-dir gunicorn uvicorn[standard] \
    && rm -rf /root/.cache/pip

COPY . .

RUN mkdir -p logs && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]

