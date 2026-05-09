FROM python:3.12-slim AS builder

WORKDIR /app

# install pg client for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

RUN pip install --upgrade pip
RUN pip install poetry

COPY common /app/common
COPY user-service/pyproject.toml user-service/poetry.lock* /app/user-service/

WORKDIR /app/user-service
RUN poetry config virtualenvs.create false && poetry install --no-root

FROM builder

WORKDIR /app

ENV PYTHONPATH=/app

COPY wait-for-db.sh /app/wait-for-db.sh
COPY common/ /app/common
COPY user-service/ /app/user-service

EXPOSE 8000
