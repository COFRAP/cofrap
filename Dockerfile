# Official release binaries, pinned and verified; no GHCR authentication required.
ARG TARGETARCH
FROM scratch AS watchdog-amd64
ADD --checksum=sha256:9dbf0b7e917526a734fc8fba3c745e557fa53e3ab8997b2615815c2e65223b5e https://github.com/openfaas/of-watchdog/releases/download/0.11.9/fwatchdog-amd64 /fwatchdog
FROM scratch AS watchdog-arm64
ADD --checksum=sha256:484e3fad21dea6b8afdf7d491be91b71050b4768395c85901ff8974241d7d869 https://github.com/openfaas/of-watchdog/releases/download/0.11.9/fwatchdog-arm64 /fwatchdog
FROM watchdog-${TARGETARCH} AS watchdog
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src/ ./src/
RUN pip install --no-cache-dir -c requirements.lock .
RUN useradd --uid 10001 --create-home app

FROM base AS frontend
USER 10001
EXPOSE 8000
CMD ["uvicorn", "cofrap.frontend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS function
ARG FUNCTION_NAME
COPY functions/${FUNCTION_NAME}/ /app/function/
RUN pip install --no-cache-dir -c requirements.lock -r /app/function/requirements.txt
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini
COPY --chmod=755 --from=watchdog /fwatchdog /usr/local/bin/fwatchdog
ENV mode=http upstream_url=http://127.0.0.1:5000 \
    fprocess="uvicorn function.handler:app --app-dir /app --host 127.0.0.1 --port 5000 --no-access-log" \
    read_timeout=60s write_timeout=60s exec_timeout=60s
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/_/health', timeout=2)"]
CMD ["fwatchdog"]
