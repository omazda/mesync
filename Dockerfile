# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./

ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build


FROM node:22-bookworm-slim AS admin-build

WORKDIR /build/admin

COPY admin/package.json admin/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY admin/ ./
COPY web/src/assets/ /build/web/src/assets/

RUN npm run build


FROM python:3.12-slim-bookworm AS python-wheels

WORKDIR /build

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels --requirement requirements.txt


FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="MeSync" \
      org.opencontainers.image.description="MAX and Telegram synchronization service"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    MESYNC_API_HOST=0.0.0.0 \
    MESYNC_API_PORT=8090

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 mesync \
    && useradd --uid 10001 --gid 10001 --create-home \
        --home-dir /home/mesync --shell /usr/sbin/nologin mesync

COPY requirements.txt ./
RUN --mount=from=python-wheels,source=/wheels,target=/wheels,ro \
    python -m pip install --no-cache-dir --no-index \
        --find-links=/wheels --requirement requirements.txt

COPY src/ ./src/
COPY run_app.py ./
COPY --from=web-build /build/web/dist ./web/dist/
COPY --from=admin-build /build/admin/dist ./admin/dist/

RUN chmod --recursive a=rX /app/src /app/web /app/admin /app/run_app.py \
    && mkdir --parents /app/data \
    && chown --recursive mesync:mesync /app/data

USER mesync

EXPOSE 8090
STOPSIGNAL SIGINT

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import json, os, urllib.request; port = os.environ.get('MESYNC_API_PORT', '8090'); health = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=4)); assert health.get('ok') is True"]

CMD ["python", "run_app.py"]
