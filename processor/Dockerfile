FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir -e . 

COPY models.py .
COPY processor ./processor
COPY logging_config.py .
COPY data ./data

CMD ["python", "-m", "processor.health"]