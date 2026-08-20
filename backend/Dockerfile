FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r senorita && useradd -r -g senorita senorita

# Install postgres client tools for healthchecks or debugging
RUN apt-get update && apt-get install -y curl postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Switch to non-root user
RUN chown -R senorita:senorita /app
USER senorita

# Expose port
EXPOSE 8000

# Health check using the /health/live endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
