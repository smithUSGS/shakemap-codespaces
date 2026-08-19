# ShakeMap + Ground Failure workshop image
FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates bzip2 && rm -rf /var/lib/apt/lists/*

ENV CONDA_DIR=/opt/conda
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    -o /tmp/mf.sh && bash /tmp/mf.sh -b -p $CONDA_DIR && rm /tmp/mf.sh && \
    $CONDA_DIR/bin/conda clean -afy && chown -R vscode:vscode $CONDA_DIR
ENV PATH=$CONDA_DIR/bin:$PATH

USER vscode
WORKDIR /home/vscode

# ShakeMap v4.4.9
RUN git clone -q --depth 1 -b v4.4.9 \
    https://code.usgs.gov/ghsc/esi/shakemap.git /home/vscode/shakemap
RUN conda env create -q -n shakemap \
    -f /home/vscode/shakemap/linux_environment.yml
RUN /opt/conda/envs/shakemap/bin/pip install -q "setuptools<82" && \
    /opt/conda/envs/shakemap/bin/pip install -q -e /home/vscode/shakemap
RUN /opt/conda/envs/shakemap/bin/pip install -q ipykernel && \
    /opt/conda/envs/shakemap/bin/python -m ipykernel install \
    --user --name shakemap --display-name "Python (ShakeMap)"

# Profile, grids, and pre-warm demo events
RUN conda run -n shakemap bash -c "sm_profile -c default -a -n"
# Download topo and Vs30 grids from GitHub release
RUN mkdir -p /home/vscode/shakemap_data/vs30 /home/vscode/shakemap_data/topo && \
    curl -L https://github.com/smithUSGS/shakemap-gf-workshop/releases/download/v1.0-data/global_vs30.grd \
         -o /home/vscode/shakemap_data/vs30/global_vs30.grd && \
    curl -L https://github.com/smithUSGS/shakemap-gf-workshop/releases/download/v1.0-data/topo_30sec.grd \
         -o /home/vscode/shakemap_data/topo/topo_30sec.grd
RUN conda run -n shakemap bash -c "sm_create ci3144585 && shake ci3144585 assemble -c 'prebuild' model contour mapping gridxml"
RUN conda run -n shakemap bash -c "sm_create us6000jlqa && shake us6000jlqa assemble -c 'prebuild' model contour mapping gridxml"
         
# Auto-activate shakemap in every terminal
RUN conda init bash -q && echo "conda activate shakemap" >> /home/vscode/.bashrc

# groundfailure (main branch, python 3.10)
RUN git clone -q --depth 1 \
    https://code.usgs.gov/ghsc/esi/groundfailure/groundfailure.git /home/vscode/groundfailure
RUN conda env create -q -n gf \
    -f /home/vscode/groundfailure/install/environment_3.10.yml
RUN /opt/conda/envs/gf/bin/python -m pip install -q -e /home/vscode/groundfailure && \
    conda clean -afy -q
RUN /opt/conda/envs/gf/bin/pip install -q ipykernel && \
    /opt/conda/envs/gf/bin/python -m ipykernel install \
    --user --name gf --display-name "Python (Ground Failure)"

# Turkey groundfailure input layers
COPY data/turkey_inputs /home/vscode/turkey_inputs
RUN printf "data_path = /home/vscode/turkey_inputs\nconfig_filepath = /home/vscode/groundfailure/defaultconfigfiles\noutput_filepath = /home/vscode/gf_output\n" \
    > /home/vscode/.gfail_defaults

# Plotting scripts
COPY data/plot_gf.py /home/vscode/plot_gf.py
COPY data/plot_gf_interactive.py /home/vscode/plot_gf_interactive.py
