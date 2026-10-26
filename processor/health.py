"""
Configures database health service API

"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from logging_config import setup_logging

import logging
import os
import psycopg2
import uvicorn

logger = logging.getLogger(__name__)
app = FastAPI(title="MarketFlow data processing service health API")

def check_database(database_url: str) -> bool:
    """
    Checks if PostgreSQL == alive 
    """
    try:
        with psycopg2.connect(database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True

    except psycopg2.Error:
        logger.exception("PSQL DB server check failed")
        return False

@app.get("/health")
def health() -> dict[str, str]: 
    """ Checks current application state """ 
    return {"status": "healthy"}
    
@app.get("/ready")
def readiness() -> JSONResponse:
    """
    Evaluates database readiness to serve traffic
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL is not configured")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready", 
                "reason": "db_configuration_missing"
            },
        )

    if not check_database(database_url):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "db_unavailable",
            },
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ready"},
    )

def main() -> None:
    setup_logging()

    logger.info("Starting MarketFlow service")
    uvicorn.run("processor.health:app", host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()