FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN npm install -g pnpm@11.25.0
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts --config.node-linker=hoisted
COPY frontend ./frontend
RUN node node_modules/vite/bin/vite.js build --config frontend/vite.config.js
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.lock.txt /app/backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt && useradd --create-home bank
COPY backend /app/backend
COPY --from=frontend /build/dist /app/dist
RUN mkdir /app/.runtime && chown -R bank:bank /app
USER bank
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
