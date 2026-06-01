#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Soul-AILab/SoulX-Podcast-1.7B",
    local_dir="/workspace/SoulX-Podcast/pretrained_models/SoulX-Podcast-1.7B",
    local_dir_use_symlinks=False,
)
print("SoulX-Podcast-1.7B downloaded")
