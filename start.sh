#!/bin/bash
echo "====================================================================="
echo "      Starting Shoe Design Recognition & Matching System"
echo "====================================================================="
echo ""

# Check python3
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "[1/3] Checking dependencies..."
$PYTHON_CMD -m pip install -r requirements.txt --quiet

echo "[2/3] Checking shoe catalog index..."
if [ ! -f "storage/shoe_index.faiss" ]; then
    echo "Initializing and indexing catalog from dataset..."
    $PYTHON_CMD -m backend.ingestion
fi

echo "[3/3] Launching ShoeMatch Web Studio at http://localhost:8000 ..."
echo ""
echo "Open your browser at: http://localhost:8000"
echo "Press Ctrl+C to stop the server."
echo "====================================================================="
echo ""

$PYTHON_CMD run_server.py
