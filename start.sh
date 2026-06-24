#!/bin/sh
set -e

uv run python -m jobs.initialize_database

exec uv run gunicorn wikidatasearch:app \
    --bind 0.0.0.0:8080 \
    -k uvicorn.workers.UvicornWorker \
    -w 6 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 10 \
    --max-requests 1000 \
    --max-requests-jitter 200 \
    --access-logfile - \
    --error-logfile -
