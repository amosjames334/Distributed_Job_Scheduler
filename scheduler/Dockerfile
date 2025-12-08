FROM python:3.9-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root

COPY scheduler/ ./scheduler/

CMD ["python", "-m", "scheduler.main"]
