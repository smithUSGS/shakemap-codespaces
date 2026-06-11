# ============================================================================
# ShakeMap workshop image - v4.4.9 built ONCE.
# ============================================================================

FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates bzip2 && rm -rf /var/lib/apt/lists/*

# --- miniforge (conda) so the install script detects an existing conda ---
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
RUN conda init bash && echo "conda activate shakemap" >> /home/vscode/.bashrc

# --- install groundfailure into its OWN env "gf" (python 3.10) ---
# (environment_3.10.yml), so 3.10 is required - 3.12 has no env file.
RUN git clone https://code.usgs.gov/ghsc/esi/groundfailure/groundfailure.git /home/vscode/groundfailure
RUN conda env create -n gf -f /home/vscode/groundfailure/install/environment_3.10.yml
RUN /opt/conda/envs/gf/bin/python -m pip install -e /home/vscode/groundfailure
RUN conda clean -afy
RUN /opt/conda/envs/gf/bin/python --version | grep -q "3.10" && /opt/conda/envs/gf/bin/gfailbin -h >/dev/null && echo "GROUNDFAILURE OK (gf env, py3.10)"

RUN conda run -n shakemap bash -c "shake -v 2>&1 | grep -q '4.4.9' && test -f /home/vscode/shakemap_data/vs30/global_vs30.grd && test -d /home/vscode/shakemap_profiles/default/data/ci3144585 && echo 'TEST PASSED'"
