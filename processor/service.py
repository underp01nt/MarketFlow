from logging_config import setup_logging

import logging
import uvicorn

logger = logging.getLogger(__name__)

def main() -> None:
    setup_logging()

    logger.info("Starting MarketFlow service")
    uvicorn.run("processor.health:app", host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()