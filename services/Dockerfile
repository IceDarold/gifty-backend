FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Scrapy spiders rely on Playwright for a number of JS-heavy sites.
# Python Playwright package does not ship browsers, so we must download them at build time.
RUN python -m playwright install --with-deps chromium

COPY . .

# Environment variables will be provided via docker-compose
ENV PYTHONPATH=/app

CMD ["python", "run_worker.py"]
