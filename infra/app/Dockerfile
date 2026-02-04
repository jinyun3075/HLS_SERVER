FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir psutil celery redis boto3 m3u8 sqlalchemy psycopg2-binary fastapi

COPY ./app ./app/