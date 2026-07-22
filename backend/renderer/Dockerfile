FROM python:3.10-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies directly including opentelemetry-resourcedetector-gcp
RUN pip install --no-cache-dir google-cloud-storage google-cloud-pubsub google-cloud-logging google-cloud-bigquery opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace opentelemetry-resourcedetector-gcp

# Copy application code
COPY main.py .

# Command to run the renderer job
CMD ["python", "main.py"]
