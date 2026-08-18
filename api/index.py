"""
Vercel Serverless Entrypoint for FastAPI Application.
"""
import sys
from pathlib import Path

# Add project root to sys.path for Vercel Python runtime
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

# Export app for Vercel
export_app = app
