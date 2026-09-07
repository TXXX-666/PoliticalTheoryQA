FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QABANK_RUNTIME_DIR=/app/runtime \
    QABANK_SOURCE_DOCX=/app/source/question_bank.docx

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app.py ./
COPY qabank ./qabank
COPY scripts ./scripts
COPY .streamlit ./.streamlit

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/runtime /app/source \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8503

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8503/_stcore/health || exit 1

CMD ["sh", "-c", "python scripts/import_docx.py --if-empty && exec python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8503 --server.headless=true --browser.gatherUsageStats=false"]
