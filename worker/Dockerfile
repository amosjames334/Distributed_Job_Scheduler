FROM python:3.9-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install docker CLI
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root

COPY worker/ ./worker/

CMD ["python", "-m", "worker.main"]
