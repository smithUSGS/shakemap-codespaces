FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates bzip2 build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV CONDA_DIR=/opt/conda
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /tmp/mf.sh \
    && bash /tmp/mf.sh -b -p $CONDA_DIR \
    && rm /tmp/mf.sh \
    && $CONDA_DIR/bin/conda clean -afy \
    && chown -R vscode:vscode $CONDA_DIR
ENV PATH=$CONDA_DIR/bin:$PATH

USER vscode

RUN conda init bash \
    && git clone --depth 1 \
        https://code.usgs.gov/ghsc/esi/shakemap.git \
        /home/vscode/shakemap-src
