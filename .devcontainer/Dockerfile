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
# ShakeMap (devel branch - matplotlib<3.11 pinned in environment.yml)
RUN git clone -q --depth 1 \
    https://code.usgs.gov/ghsc/esi/shakemap.git /home/vscode/shakemap
RUN conda create -q -y -n conda-lock -c conda-forge conda-lock
RUN CONDA_LOCK_NO_MAMBA=1 conda run -n conda-lock conda-lock install \
    --name shakemap /home/vscode/shakemap/conda-lock.yml
RUN /opt/conda/envs/shakemap/bin/pip install -q --no-deps -e /home/vscode/shakemap
RUN conda env remove -q -y -n conda-lock
RUN /opt/conda/envs/shakemap/bin/pip install -q ipykernel && \
    /opt/conda/envs/shakemap/bin/python -m ipykernel install \
    --user --name shakemap --display-name "Python (ShakeMap)"
# Create ShakeMap profile
RUN conda run -n shakemap bash -c "sm_profile -c default -a -n"
# Download topo and Vs30 grids from GitHub release
RUN mkdir -p /home/vscode/shakemap_data/vs30 /home/vscode/shakemap_data/topo && \
    curl -L https://github.com/smithUSGS/shakemap-gf-workshop/releases/download/v1.0-data/global_vs30.grd \
         -o /home/vscode/shakemap_data/vs30/global_vs30.grd && \
    curl -L https://github.com/smithUSGS/shakemap-gf-workshop/releases/download/v1.0-data/topo_30sec.grd \
         -o /home/vscode/shakemap_data/topo/topo_30sec.grd
RUN sed -i \
    's|vs30file = .*|vs30file = /home/vscode/shakemap_data/vs30/global_vs30.grd|' \
    /home/vscode/shakemap_profiles/default/install/config/model.conf && \
    sed -i \
    's|.*topography = .*|      topography = /home/vscode/shakemap_data/topo/topo_30sec.grd|' \
    /home/vscode/shakemap_profiles/default/install/config/products.conf
# AFAD regional Vs30 for Turkey
COPY data/vs30/vs30_turkey_300m.tif /home/vscode/shakemap_data/vs30/afad_turkey_vs30.tif
# Pre-cache NaturalEarth cartopy data
RUN conda run -n shakemap python -c "import cartopy.io.shapereader as s; s.natural_earth(resolution='10m', category='cultural', name='admin_0_countries'); s.natural_earth(resolution='10m', category='cultural', name='admin_1_states_provinces_lines'); s.natural_earth(resolution='10m', category='physical', name='lakes'); s.natural_earth(resolution='10m', category='physical', name='ocean'); s.natural_earth(resolution='10m', category='physical', name='land')"
# Pre-stage workshop events
COPY data/event_configs /home/vscode/event_configs_src
RUN mkdir -p \
    /home/vscode/shakemap_profiles/default/data/bssc2014nsanandreassapsassha_m7p6_se/current \
    /home/vscode/shakemap_profiles/default/data/malatya_fault_se/current \
    /home/vscode/shakemap_profiles/default/data/us6000jllz/current && \
    cp -r /home/vscode/event_configs_src/bssc2014nsanandreassapsassha_m7p6_se/. /home/vscode/shakemap_profiles/default/data/bssc2014nsanandreassapsassha_m7p6_se/current/ && \
    cp -r /home/vscode/event_configs_src/malatya_fault_se/. /home/vscode/shakemap_profiles/default/data/malatya_fault_se/current/ && \
    cp -r /home/vscode/event_configs_src/us6000jllz/. /home/vscode/shakemap_profiles/default/data/us6000jllz/current/
# Warm up shake's first-run import cache (known slow first invocation)
RUN conda run -n shakemap shake -v || true
# Auto-activate shakemap in every terminal
RUN conda init bash -q && echo "conda activate shakemap" >> /home/vscode/.bashrc
# groundfailure
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
# plotting scripts
COPY data/plot_gf.py /home/vscode/plot_gf.py
COPY data/plot_gf_interactive.py /home/vscode/plot_gf_interactive.py
