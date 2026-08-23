# Python 3.11: requirements.txt caps torch at <2.3.0,
# and torch 2.2.x ships no wheels for 3.12+. 3.11 is the newest base the
# pin allows. Raise both together or not at all.
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install system dependencies required for OpenCV, PyTorch, FAISS & SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install Python packages (using CPU wheels for PyTorch)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p storage/catalog_images storage/models storage/uploads

EXPOSE 8000

# Start server using Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

