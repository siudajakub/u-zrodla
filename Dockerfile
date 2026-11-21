FROM python:3.12-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 INVESTWATCH_STATE=/state
COPY api/requirements.lock /tmp/investwatch-requirements
RUN pip install --no-cache-dir -r /tmp/investwatch-requirements
COPY api/ api/
COPY analysis/ analysis/
COPY collectors/ collectors/
COPY web/ web/
COPY data/probe-snapshots/ data/probe-snapshots/
COPY tools/watch_sources.py tools/watch_sources.json tools/
RUN useradd --create-home --uid 10001 investwatch && mkdir /state && chown investwatch /state
USER investwatch
CMD ["python","-m","uvicorn","api.server:app","--host","0.0.0.0","--port","8769"]
