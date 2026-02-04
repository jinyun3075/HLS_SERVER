FROM python:3.11-slim

RUN apt-get update && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir sqlalchemy psycopg2-binary psutil uvicorn fastapi boto3 python-multipart

COPY ./app/manager ./app/manager/
COPY ./app/core ./app/core/
COPY ./app/services ./app/services/