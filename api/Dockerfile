FROM python:3.9-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root

COPY api/ ./api/

CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
