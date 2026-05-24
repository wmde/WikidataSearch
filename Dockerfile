FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential g++ make cmake python3-dev pkg-config libgomp1 curl ca-certificates gnupg && \
    rm -rf /var/lib/apt/lists/*

# Install supercronic for container-friendly cron scheduling
ARG SUPERCRONIC_VERSION=v0.2.38
RUN curl -fsSLo /usr/local/bin/supercronic \
    "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" && \
    chmod +x /usr/local/bin/supercronic

# Setup the app in workspace
WORKDIR /workspace

# Install node from upstream
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash
RUN apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install node package manager yarn
RUN npm install -g yarn

# Install frontend dependencies and build frontend
COPY frontend/package.json frontend/yarn.lock ./frontend/
RUN cd frontend && yarn install
COPY frontend ./frontend
RUN cd frontend && yarn build

# Install backend dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY wikidatasearch ./wikidatasearch
COPY jobs ./jobs

# Container start script
CMD [ "uv", "run", "gunicorn", "wikidatasearch:app", "--bind", "0.0.0.0:8080", \
    "-k", "uvicorn.workers.UvicornWorker", "-w", "6", \
    "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "10", \
    "--max-requests", "1000", "--max-requests-jitter", "200", \
    "--access-logfile", "-", "--error-logfile", "-" ]
