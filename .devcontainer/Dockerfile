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

# ShakeMap (main branch)
RUN git clone -q --depth 1 https://code.usgs.gov/ghsc/esi/shakemap.git /home/vscode/shakemap
RUN conda env create -q -n shakemap -f /home/vscode/shakemap/linux_environment.yml
RUN mkdir -p ~/.config/matplotlib && echo "backend : Agg" > ~/.config/matplotlib/matplotlibrc
RUN /opt/conda/envs/shakemap/bin/pip install -q "setuptools<82" && \
    /opt/conda/envs/shakemap/bin/pip install -q -e /home/vscode/shakemap
RUN /opt/conda/envs/shakemap/bin/pip install -q ipykernel && \
    /opt/conda/envs/shakemap/bin/python -m ipykernel install \
    --user --name shakemap --display-name "Python (ShakeMap)"

RUN conda run -n shakemap bash -c "\
    sm_profile -c default -a > /dev/null 2>&1 && \
    sm_create ci3144585 > /dev/null 2>&1 && \
    shake ci3144585 assemble -c 'prebuild' model contour mapping gridxml > /dev/null 2>&1 && \
    sm_create us6000jlqa > /dev/null 2>&1 && \
    shake us6000jlqa assemble -c 'prebuild' model contour mapping gridxml > /dev/null 2>&1"

RUN conda init bash -q && echo "conda activate shakemap" >> /home/vscode/.bashrc

# groundfailure (python 3.10)
RUN git clone -q --depth 1 https://code.usgs.gov/ghsc/esi/groundfailure/groundfailure.git /home/vscode/groundfailure
RUN conda env create -q -n gf -f /home/vscode/groundfailure/install/environment_3.10.yml
RUN /opt/conda/envs/gf/bin/python -m pip install -q -e /home/vscode/groundfailure && \
    conda clean -afy -q
RUN /opt/conda/envs/gf/bin/pip install -q ipykernel && \
    /opt/conda/envs/gf/bin/python -m ipykernel install \
    --user --name gf --display-name "Python (Ground Failure)"

# Turkey groundfailure input layers + defaults
COPY data/turkey_inputs /home/vscode/turkey_inputs
RUN printf "data_path = /home/vscode/turkey_inputs\nconfig_filepath = /home/vscode/groundfailure/defaultconfigfiles\noutput_filepath = /home/vscode/gf_output\n" \
    > /home/vscode/.gfail_defaults

# Plotting scripts
COPY data/plot_gf.py /home/vscode/plot_gf.py
COPY data/plot_gf_interactive.py /home/vscode/plot_gf_interactive.py

# Test
RUN conda run -n shakemap bash -c "\
    shake -v > /dev/null 2>&1 && \
    test -f /home/vscode/shakemap_data/vs30/global_vs30.grd && \
    test -d /home/vscode/shakemap_profiles/default/data/ci3144585 && \
    test -d /home/vscode/shakemap_profiles/default/data/us6000jlqa && \
    test -f /home/vscode/shakemap_profiles/default/data/ci3144585/current/products/grid.xml && \
    test -f /home/vscode/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml && \
    test -f /home/vscode/turkey_inputs/Nowicki2014_X.tif && \
    test -f /home/vscode/turkey_inputs/Jessee2018_X.tif && \
    test -f /home/vscode/turkey_inputs/global_grad.tif && \
    test -f /home/vscode/plot_gf.py && \
    test -f /home/vscode/plot_gf_interactive.py && \
    test -f /home/vscode/.gfail_defaults && \
    echo 'TEST PASSED'"
