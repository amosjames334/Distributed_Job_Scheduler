FROM python:3.9-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root

COPY worker/ ./worker/

CMD ["python", "-m", "worker.main"]
