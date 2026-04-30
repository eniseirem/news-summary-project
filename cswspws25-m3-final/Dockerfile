FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    wget \
    curl \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir inside the container
WORKDIR /app

# Copy requirements (relative to build context ".")
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy the src directory
COPY src ./src

# (Optional) download spaCy model
# RUN python -m spacy download en_core_web_sm

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "1800", "--timeout-graceful-shutdown", "30"]
