"""
Server Launcher for Shoe Design Recognition & Matching System.
"""
import uvicorn
from backend.config import HOST, PORT, DEBUG

if __name__ == "__main__":
    print("=" * 65)
    print("   Starting Shoe Design Recognition & Matching System   ")
    print(f"   Listening on: http://{HOST}:{PORT}")
    print("=" * 65)
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=DEBUG)
