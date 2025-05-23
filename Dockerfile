FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY learnmcp_xapi/ ./learnmcp_xapi/
COPY schemas/ ./schemas/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Run application
CMD ["python", "-m", "learnmcp_xapi.main"]