#!/usr/bin/env python3
"""
Script to run the API server
"""
import sys
from pathlib import Path
import uvicorn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.config import settings
from politia.models import init_db


def main():
    """Run the API server"""
    # Initialize database on startup
    init_db()
    
    uvicorn.run(
        "politia.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # Enable auto-reload in development
    )


if __name__ == "__main__":
    main()






