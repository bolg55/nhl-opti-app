# Stage 1: Build frontend
FROM node:22-slim AS frontend
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.13-slim-bookworm
WORKDIR /app

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY seed_data/ seed_data/
COPY --from=frontend /app/dist dist/

RUN useradd -r -s /bin/false appuser
USER appuser

ENV PORT=8000
ENV DATA_DIR=/app/data
EXPOSE $PORT

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
