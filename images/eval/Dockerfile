FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime AS build

RUN python -m venv --system-site-packages /opt/milk-venv \
 && /opt/milk-venv/bin/pip install --no-cache-dir \
      boto3==1.40.40 \
      https://github.com/huggingface/transformers/archive/ac3244569528944b9d5773cafea525cd8a8b63de.zip \
      torchao==0.15.0 \
      zstandard==0.25.0

FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/milk-venv/bin:$PATH \
    CC=/usr/bin/gcc \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

COPY --from=build /opt/milk-venv /opt/milk-venv
COPY evaluate.py /opt/milk/evaluate.py

ENTRYPOINT ["python", "/opt/milk/evaluate.py"]
