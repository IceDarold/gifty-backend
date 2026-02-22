FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1 \
    PYTHONUNBUFFERED 1

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files and set ownership
COPY --chown=appuser:appuser . .

# Make start script executable
RUN chmod +x scripts/start.sh

# Use the non-root user
USER appuser

# Expose port
EXPOSE 8000

# Start command
CMD ["./scripts/start.sh"]
