# Backend image: FastAPI + Alembic on Python 3.12.
# Build context is ./backend. Only runtime code is copied (no tests, no .venv).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Unprivileged user: the process never needs to write anything inside /srv.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /srv --shell /usr/sbin/nologin app

# Dependencies first, so code changes do not invalidate the pip layer.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini entrypoint.sh ./

USER app

EXPOSE 8000

# Run through `sh` so the script does not depend on the executable bit.
ENTRYPOINT ["sh", "/srv/entrypoint.sh"]
