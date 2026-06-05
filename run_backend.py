#!/usr/bin/env python3
"""Entry point: initialises DB, seeds themes, starts FastAPI via uvicorn."""
import uvicorn
from backend import config

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level="info",
    )
