FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY src/ src/
COPY data/ data/
COPY local_sharepoint/ local_sharepoint/

EXPOSE 8000 8501

CMD ["uvicorn", "src.mock_itsm.main:app", "--host", "0.0.0.0", "--port", "8000"]
