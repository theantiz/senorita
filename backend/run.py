import argparse
import sys
import os
from pathlib import Path

# Add backend directory to path so imports work correctly
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from app.main import app
from app.core.config import settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Señorita Backend")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Port to run the backend on")
    args = parser.parse_args()

    # When running as an executable built by PyInstaller, uvicorn auto-reload doesn't work.
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        reload=False,
    )
