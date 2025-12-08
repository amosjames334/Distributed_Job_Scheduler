FROM python:3.9-slim

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev, no interaction, no root package)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root

COPY api/ ./api/

# We need to run from root to import properly if using absolute imports, 
# but here code is in api/app.
# Adjusting to run uvicorn from /app
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
