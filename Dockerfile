# ---- Builder Stage ----
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json vite.config.js ./
COPY static_src ./static_src

RUN npm ci && npm run build

# ---- Final Stage ----
FROM python:3.11-alpine

RUN addgroup -S app && adduser -S app -G app && \
    apk add --no-cache gcc musl-dev curl

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=builder /build/static/dist ./static/dist
RUN chown -R app:app /code

USER app

ENV PYTHONUNBUFFERED=1

EXPOSE 8989

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8989/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8989", "--workers", "4", "--log-level", "info"]
