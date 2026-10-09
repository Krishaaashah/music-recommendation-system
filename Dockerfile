# Multi-stage Dockerfile for FastAPI Backend and Streamlit Dashboard
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY backend/ ./backend/
COPY api/ ./api/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY output/ ./output/
COPY streamlit_app.py .

EXPOSE 8000 8501

# Default command starts FastAPI backend
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
