FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF extraction and URL scraping
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir requests beautifulsoup4

COPY . .

# Create volume mount points for input and output
RUN mkdir -p /data/input /data/output

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default entrypoint
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
