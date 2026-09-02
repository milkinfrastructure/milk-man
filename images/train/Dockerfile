FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2 AS build

RUN python -m venv --system-site-packages /opt/milk-venv \
 && /opt/milk-venv/bin/pip install --no-cache-dir \
      boto3==1.40.40 \
      https://github.com/huggingface/transformers/archive/ac3244569528944b9d5773cafea525cd8a8b63de.zip \
      zstandard==0.25.0

FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2

ENV PATH=/opt/milk-venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

COPY --from=build /opt/milk-venv /opt/milk-venv
COPY train.py /opt/milk/train.py

ENTRYPOINT ["python", "/opt/milk/train.py"]
