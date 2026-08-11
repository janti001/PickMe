# Dockerfile — local Docker/Podman build of PickMe-EM.
#
# This mirrors container/PickMe.def as closely as Docker's syntax allows.
# Keep the two in step: same base image tag, same apt package list, same
# "build the env from PickMe.yml" step. If you change one, change the other.
#
# HPC clusters generally do NOT allow Docker (it needs a root-owned daemon).
# This file exists for:
#   1. Local use on your own Linux/WSL/macOS machine via Docker Desktop or
#      Podman, where Apptainer may not be installed.
#   2. Producing an image that Apptainer/Singularity can convert on a
#      machine where you DO have Apptainer, without needing root:
#        apptainer build PickMe.sif docker-daemon://pickme-em:local
#      (build the Docker image first, then run that from the repo root).
#
# Build from the REPO ROOT, not from inside container/, because COPY paths
# below are resolved relative to the Docker build context:
#   docker build -f container/Dockerfile -t pickme-em:local .

#FROM condaforge/miniforge3:26.3.2-3
FROM --platform=linux/amd64 condaforge/miniforge3:26.3.2-3
# Pinned to match container/PickMe.def — see the comment there for why.

ENV DEBIAN_FRONTEND=noninteractive

# --- X11 / OpenGL libraries for the napari + Qt6 GUI (choose_objects) ------
# Same list as container/PickMe.def, verified against packages.ubuntu.com
# for noble (24.04), which is what condaforge/miniforge3:26.3.2-3 is built
# on. See docs/gui-setup.md for what breaks without these.
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libgl1 \
        libegl1 \
        libopengl0 \
        libglx0 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libx11-xcb1 \
        libdbus-1-3 \
        libfontconfig1 \
        libfreetype6 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libxi6 \
        libsm6 \
        libice6 \
        mesa-utils \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/PickMe

# Only what `pip --no-deps -e .` and `conda env create` need — see
# container/PickMe.def's %files comment for why this list, not the whole repo.
COPY PickMe.yml pyproject.toml README.md LICENSE ./
COPY src/PickMe ./src/PickMe

# Single source of truth for dependencies: build the env straight from
# PickMe.yml. This also runs PickMe.yml's "pip: --no-deps -e ." line, which
# resolves "." against WORKDIR (/opt/PickMe) — correct, since that's where
# the COPY above put pyproject.toml and src/.
RUN conda env create -f PickMe.yml && \
    conda clean --all --yes

# Build-time smoke test — fail the image build here, not in a user's hands.
RUN /opt/conda/envs/PickMe/bin/python -m compileall /opt/PickMe/src/PickMe && \
    /opt/conda/envs/PickMe/bin/PickMe -h && \
    /opt/conda/envs/PickMe/bin/PickMe filter_objects -h && \
    /opt/conda/envs/PickMe/bin/PickMe choose_objects -h && \
    /opt/conda/envs/PickMe/bin/PickMe particle_extraction -h && \
    /opt/conda/envs/PickMe/bin/PickMe decompress -h && \
    /opt/conda/envs/PickMe/bin/PickMe convert -h

ENV CONDA_ENV=PickMe
ENV PATH=/opt/conda/envs/PickMe/bin:${PATH}
# See container/PickMe.def %environment for why xcb and MPLBACKEND=Agg.
ENV QT_QPA_PLATFORM=xcb
ENV MPLBACKEND=Agg

ENTRYPOINT ["PickMe"]
CMD ["-h"]
