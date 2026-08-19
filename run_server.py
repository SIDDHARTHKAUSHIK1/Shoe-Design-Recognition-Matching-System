"""
Server Launcher for Shoe Design Recognition & Matching System.
"""
import os
import uvicorn
from backend.config import HOST, PORT, DEBUG

if __name__ == "__main__":
    workers = int(os.getenv("WORKERS", "1"))
    print("=" * 65)
    print("   Starting Shoe Design Recognition & Matching System   ")
    print(f"   Listening on: http://{HOST}:{PORT} (Workers: {workers})")
    print("=" * 65)
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        workers=workers,
        reload=DEBUG,
        access_log=False
    )
