FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git curl && apt-get clean

RUN ln -s /usr/bin/python3 /usr/bin/python
