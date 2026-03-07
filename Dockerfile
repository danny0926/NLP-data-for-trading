# PAM — Political Alpha Monitor
# Multi-stage Docker build for lightweight deployment

FROM python:3.12-slim AS base

WORKDIR /app

# System deps for Playwright + building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl git \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements_v3.txt requirements_dashboard.txt ./
RUN pip install --no-cache-dir \
    -r requirements_v3.txt \
    -r requirements_dashboard.txt \
    google-genai beautifulsoup4 PyMuPDF playwright pydantic fastapi uvicorn

# Install Playwright Chromium (for Senate ETL)
RUN python -m playwright install chromium --with-deps

# Copy source
COPY src/ ./src/
COPY data/ ./data/
COPY *.py ./
COPY .env .env

# Expose ports: Streamlit (8501), FastAPI (8000)
EXPOSE 8501 8000

# Default: run Streamlit dashboard
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
