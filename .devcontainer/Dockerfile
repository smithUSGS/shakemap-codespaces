# ============================================================================
# ShakeMap workshop image - v4.4.9
# ============================================================================

FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates bzip2 && rm -rf /var/lib/apt/lists/*

ENV CONDA_DIR=/opt/conda
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /tmp/mf.sh && bash /tmp/mf.sh -b -p $CONDA_DIR && rm /tmp/mf.sh && $CONDA_DIR/bin/conda clean -afy && chown -R vscode:vscode $CONDA_DIR
ENV PATH=$CONDA_DIR/bin:$PATH

USER vscode
WORKDIR /home/vscode

ARG SHAKEMAP_VERSION=v4.4.9

RUN curl -fsSL "https://code.usgs.gov/ghsc/esi/shakemap/-/raw/${SHAKEMAP_VERSION}/scripts/install_shakemap.sh" -o /home/vscode/install_shakemap.sh && chmod +x /home/vscode/install_shakemap.sh

RUN bash /home/vscode/install_shakemap.sh -v ${SHAKEMAP_VERSION} -k /home/vscode/shakemap-src && conda clean -afy

RUN conda run -n shakemap sm_profile -c default -a

RUN conda run -n shakemap bash -c "sm_create ci3144585 && shake ci3144585 assemble -c 'prebuild' model contour mapping"

RUN test -d /home/vscode/.local/share/cartopy/shapefiles/natural_earth && echo "CARTOPY BASEMAPS BAKED IN"

RUN echo "conda activate shakemap" >> /home/vscode/.bashrc

RUN conda run -n shakemap bash -c "shake -v 2>&1 | grep -q '4.4.9' && test -f /home/vscode/shakemap_data/vs30/global_vs30.grd && test -d /home/vscode/shakemap_profiles/default/data/ci3144585 && echo 'TEST PASSED'"
