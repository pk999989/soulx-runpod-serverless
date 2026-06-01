FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    SOULX_DIR=/workspace/SoulX-Podcast \
    SOULX_MODEL_PATH=/workspace/SoulX-Podcast/pretrained_models/SoulX-Podcast-1.7B

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Soul-AILab/SoulX-Podcast.git /workspace/SoulX-Podcast

WORKDIR /workspace/SoulX-Podcast

RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install "huggingface_hub>=0.34.0,<1.0" hf_transfer runpod && \
    pip uninstall -y torchvision && \
    pip install --no-cache-dir torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126

COPY download_model.py /workspace/download_model.py
RUN python /workspace/download_model.py

COPY handler.py /workspace/handler.py

WORKDIR /workspace
CMD ["python", "-u", "/workspace/handler.py"]
