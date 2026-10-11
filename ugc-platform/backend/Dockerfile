FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-inter fontconfig \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY ugc_studio ./ugc_studio
# KittenTTS's text frontend (misaki[en]) drags in CUDA PyTorch that KittenTTS
# never uses (it runs on ONNX Runtime). Removing it in the same layer keeps the
# image ~5 GB smaller.
RUN pip install --no-cache-dir '.[claude,kitten]' \
 && pip uninstall -y torch triton spacy-curated-transformers curated-transformers curated-tokenizers \
 && pip freeze | grep -E '^nvidia-' | cut -d= -f1 | xargs -r pip uninstall -y

# Bake the voice model into the image so the first ad doesn't wait on a download.
ENV HF_HOME=/opt/hf
RUN python -c "from kittentts import KittenTTS; KittenTTS('KittenML/kitten-tts-mini-0.8')" \
 && chmod -R a+rX /opt/hf

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
ENV UGC_DATA_DIR=/data
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["uvicorn", "ugc_studio.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
