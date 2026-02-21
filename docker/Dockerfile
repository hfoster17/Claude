FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy engine code
COPY engine/ .

# Create directories for mounts
RUN mkdir -p /app/models /app/data /app/logs

EXPOSE 5555

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',5555)); s.close()" || exit 1

ENTRYPOINT ["python", "main.py", "--serve"]
CMD ["--host", "0.0.0.0", "--port", "5555", "--model-dir", "/app/models", "--log-dir", "/app/logs"]
