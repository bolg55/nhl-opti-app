# Stage 1: Build frontend
FROM node:20-slim AS frontend
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY seed_data/ seed_data/
COPY --from=frontend /app/dist dist/

ENV PORT=8000
ENV DATA_DIR=/app/data
EXPOSE $PORT

CMD uvicorn server.main:app --host 0.0.0.0 --port $PORT
