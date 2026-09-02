FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2 AS build

RUN python -m venv --system-site-packages /opt/milk-venv \
 && /opt/milk-venv/bin/pip install --no-cache-dir \
      https://github.com/huggingface/transformers/archive/ac3244569528944b9d5773cafea525cd8a8b63de.zip \
      torchao==0.15.0

FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/* /root/.cache

ENV PATH=/opt/milk-venv/bin:$PATH \
    CC=/usr/bin/gcc \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

COPY --from=build /opt/milk-venv /opt/milk-venv
COPY server.py /opt/milk/server.py

ENTRYPOINT ["python", "/opt/milk/server.py"]
