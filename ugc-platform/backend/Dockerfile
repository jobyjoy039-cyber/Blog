FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-inter fontconfig \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY ugc_studio ./ugc_studio
RUN pip install --no-cache-dir '.[claude]'

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
ENV UGC_DATA_DIR=/data
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["uvicorn", "ugc_studio.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
