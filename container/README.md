# Running PickMe-EM in a container

This solves the install problem described in `../docs/gui-setup.md`: conda
solving badly, pip mixing incompatible Qt libraries, and the napari GUI
failing on WSL and HPC. The container has the whole stack — including the
Linux X11/OpenGL libraries the GUI needs — baked in and frozen at build
time, so it either works the same way every time, or it fails in the same
documented way every time.

**HPC clusters do not give you root.** Docker needs a root-owned daemon, so
it is not usable there. **Apptainer/Singularity** is the tool this README
is written around; it runs as your own user and needs no daemon. `Dockerfile`
is provided for people who prefer building locally with Docker/Podman first
(see "Building the image" below for how that still gets you a `.sif`).

If you are new to containers: think of `PickMe.sif` as one file containing
an entire mini Linux install with PickMe and everything it depends on
already set up correctly inside it. You don't install anything into it
yourself — you just run commands "inside" it.

---

## Building the image, or getting a prebuilt one

**There is no prebuilt image published yet** — this repo does not currently
have CI wired up to build and publish one automatically (that is proposed,
not done, in `../docs/deployment-plan.md` Plan D). Until that exists, build
it yourself:

```bash
cd PickMe            # the repo root
./container/build.sh
```

This produces `container/PickMe.sif`. Building takes a few minutes (conda
solving the environment is the slow part) and needs either real root or a
working `--fakeroot` — see the comments in `build.sh` if you hit a
permissions error, especially on an HPC login node where you typically have
neither. The short version: **build it once on your own Linux/WSL machine,
then copy the resulting `.sif` to the cluster** — running a `.sif` never
needs root, only building one does.

```bash
# on your own machine
./container/build.sh

# copy it to the cluster
scp container/PickMe.sif myuser@cluster.example.edu:/scratch/myuser/
```

If you only have Docker available locally (e.g. Docker Desktop on a
Windows/Mac laptop), build the Docker image and convert it:

```bash
docker build -f container/Dockerfile -t pickme-em:local .
apptainer build container/PickMe.sif docker-daemon://pickme-em:local
```

While iterating on `container/PickMe.def` itself, build a `--sandbox`
(a plain directory, not a compressed `.sif`) — it rebuilds faster and you
can shell into it to debug a failed step:

```bash
./container/build.sh --sandbox
apptainer shell --writable container/PickMe.sandbox
```

---

## The three ways to run a container

Whichever runtime you use, there are three modes. Knowing which you want saves
a lot of confusion.

| Mode | Apptainer | Docker | Use when |
|---|---|---|---|
| **Run** — the built-in entry point | `apptainer run PickMe.sif <args>` | `docker run pickme-em:local <args>` | Normal use. `<args>` go straight to `PickMe` |
| **Exec** — any command inside | `apptainer exec PickMe.sif PickMe <args>` | `docker run --entrypoint PickMe pickme-em:local <args>` | Scripts, SLURM jobs, or running `python`/`ls` inside |
| **Shell** — an interactive prompt | `apptainer shell PickMe.sif` | `docker run --rm -it --entrypoint bash pickme-em:local` | Exploring, debugging, running several commands in a row |

These are equivalent for PickMe:

```bash
apptainer run  PickMe.sif filter_objects --input-dir ./segs --non-interactive
apptainer exec PickMe.sif PickMe filter_objects --input-dir ./segs --non-interactive
```

`exec` is used throughout the examples below because it is explicit about what
is being run — worth the extra word in a script someone else has to read.

### Where do my files go?

This is the one thing that catches everybody. A container has its own
filesystem; the host's directories are not visible inside unless you say so.

**Apptainer** automatically makes available:

- your `$HOME`
- the directory you launched from (and it keeps it as the working directory)

so anything under those just works. Anything else — `/scratch`, `/gpfs`, a
project volume — needs `--bind /path`.

**Docker** shares *nothing* by default and starts in `/opt/PickMe` inside the
image. You must both mount your data with `-v` **and** set the working
directory with `-w`:

> **Docker gotcha.** PickMe writes its results to `./outputs` relative to the
> working directory. With Docker's default working directory that is
> `/opt/PickMe/outputs` — **inside the container**, which is destroyed when the
> command finishes. Your results are silently gone. Always pass `-w` to a
> mounted directory, or use `--output-dir`. Apptainer keeps your host working
> directory, so it does not have this problem.

---

## Using Docker directly

Docker is fine on your own machine. It is **not** usable on most HPC clusters,
which do not give you root — use Apptainer there.

### Build

```bash
cd PickMe                 # the repo root, NOT container/
docker build -f container/Dockerfile -t pickme-em:local .
```

The trailing `.` matters: it sets the build context to the repo root, which is
where the `Dockerfile` expects to find `PickMe.yml` and `src/`.

### Run a headless subcommand

```bash
docker run --rm \
    -v /path/on/host/pickme_project:/data \
    -w /data \
    --user "$(id -u):$(id -g)" \
    pickme-em:local \
    filter_objects --input-dir /data/segmentations --non-interactive
```

| Flag | Why |
|---|---|
| `--rm` | Delete the stopped container afterwards. Without it they pile up |
| `-v host:container` | Mount your data. The left side is the host path, the right is where it appears inside |
| `-w /data` | Work from the mounted directory, so `./outputs` lands on the host — see the gotcha above |
| `--user "$(id -u):$(id -g)"` | Run as you. Without it Docker runs as root and **every output file is owned by root on your host**, which you then need `sudo` to delete |
| `pickme-em:local` | The image |
| `filter_objects ...` | Appended to the image's `ENTRYPOINT ["PickMe"]`, so no `PickMe` needed |

### Get a shell inside

```bash
docker run --rm -it \
    -v /path/on/host/pickme_project:/data \
    -w /data \
    --user "$(id -u):$(id -g)" \
    --entrypoint bash \
    pickme-em:local
```

`--entrypoint bash` overrides `ENTRYPOINT ["PickMe"]`; without it Docker tries
to run `PickMe bash`. `-it` gives an interactive terminal — needed both for the
shell and for any subcommand you want to answer prompts on.

### The GUI under Docker (Linux hosts)

```bash
xhost +local:docker          # allow the container to talk to your X server
docker run --rm -it \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v /path/on/host/pickme_project:/data \
    -w /data \
    --user "$(id -u):$(id -g)" \
    pickme-em:local \
    choose_objects --input-dir /data/tomograms
xhost -local:docker          # revoke it again afterwards
```

Add `--gpus all` if you have the NVIDIA Container Toolkit installed and want
hardware rendering.

On **Docker Desktop for Mac or Windows** the GUI is considerably more awkward —
the container cannot reach your display without a separate X server (XQuartz,
VcXsrv) and host networking configuration. If you are on Windows, run PickMe
through **WSL2** instead and use Apptainer or native conda there. If you are on
a Mac, install with conda directly; there is no display problem to solve.

---

## Working inside the container

For an interactive picking session it is often easier to open a shell once and
run several commands, rather than prefixing each with `apptainer exec`.

```bash
cd /scratch/$USER/pickme_project      # where your data lives
apptainer shell --bind /scratch/$USER /scratch/$USER/PickMe.sif
```

The prompt changes to `Apptainer>`. You are now inside, as yourself, with your
working directory preserved:

```
Apptainer> which PickMe
/opt/conda/envs/PickMe/bin/PickMe

Apptainer> pwd
/scratch/myuser/pickme_project

Apptainer> ls
segmentations/  tomograms/

Apptainer> PickMe filter_objects --input-dir ./segmentations
    1. TS_1001_segment.mrc
    2. TS_1002_segment.mrc
Which files? (all / 1,2 / 1-2):  all
...
Apptainer> ls outputs/filter/
job001/

Apptainer> exit
```

Notes for working this way:

- **The conda environment is already active.** There is no `conda activate` to
  run — `PATH` points at the environment inside the image. If `conda activate`
  seems necessary, you are not actually inside the container.
- **Prompts work normally**, because you have a terminal. This is the one place
  `--non-interactive` is *not* needed. Use it in `sbatch` scripts, where there
  is no terminal and `input()` raises `EOFError`.
- **The image is read-only.** You cannot `pip install` into it. To change
  dependencies, edit `../PickMe.yml` and rebuild.
- **Files you create belong to you** under Apptainer, and land on the host as
  normal. Under Docker they belong to root unless you passed `--user`.
- **`exit` leaves the container.** Anything written outside a bound/mounted
  directory is discarded.

---

## Running the headless subcommands

Four of the five subcommands are headless compute and need no display:
`filter_objects`, `particle_extraction`, `decompress`, `convert`.

Apptainer automatically bind-mounts your `$HOME` and the current working
directory, and runs as you (not as some container-internal user), so paths
under those "just work". Data living elsewhere — `/scratch`, `/gpfs`, a
shared project volume — needs an explicit `--bind`.

```bash
apptainer exec container/PickMe.sif \
    PickMe filter_objects --input-dir /scratch/myuser/segmentations --non-interactive
```

### Complete SLURM `sbatch` script

Copy-paste and edit the `#SBATCH` lines and paths for your cluster.

```bash
#!/bin/bash
#SBATCH --job-name=pickme
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=pickme_%j.log

set -euo pipefail

SIF=/scratch/$USER/PickMe.sif
DATA=/scratch/$USER/pickme_project

# --bind exposes $DATA inside the container at the same path. Add more
# --bind flags (comma-separated, or repeat the flag) for any other
# directory outside $HOME/$PWD that your data lives in.
apptainer exec --bind "${DATA}" "${SIF}" \
    PickMe filter_objects --input-dir "${DATA}/segmentations" --non-interactive

# `choose_objects` (the GUI step) cannot run in a batch job — no compute
# node has a display attached, no matter how PickMe is installed. Run it
# interactively between these two batch stages: ssh -X to a login node or
# an interactive job (see "Running the GUI" below), pick your objects, then
# submit this second batch stage against the choose/jobNNN output it wrote.
apptainer exec --bind "${DATA}" "${SIF}" \
    PickMe particle_extraction --output-dir "${DATA}/outputs" --sample-rate 20
```

Submit with `sbatch this_script.sh`.

---

## Running the GUI subcommand (`choose_objects`) with X11 forwarding

`choose_objects` opens a napari + Qt6 window. The container has the Qt6/GUI
libraries; it still needs a display to draw into, exactly as in
`../docs/gui-setup.md` §2 — the container doesn't change that requirement,
it only guarantees the libraries needed to talk to whatever display you
give it are present and at the right versions.

**Prerequisite** (same as the non-container case): you need a working
`$DISPLAY` before you touch the container at all. `ssh -X`/`-Y` to a login
or interactive node, WSLg, or a VNC session all provide one. Check with
`echo $DISPLAY` — if it prints nothing, fix that first; nothing below will
help until it does.

```bash
apptainer exec \
    --bind /tmp/.X11-unix \
    --env DISPLAY="${DISPLAY}" \
    --env XAUTHORITY="${XAUTHORITY}" \
    --bind "${XAUTHORITY}" \
    container/PickMe.sif \
    PickMe choose_objects --input-dir /scratch/myuser/tomograms
```

What each piece does:

| Flag | Why |
|---|---|
| `--bind /tmp/.X11-unix` | The X11 socket directory. Without it the container can't reach the X server at all — you'll see the `xcb` platform plugin failure from `../docs/gui-setup.md`. |
| `--env DISPLAY="${DISPLAY}"` | Apptainer does not forward host environment variables by default; `DISPLAY` has to be passed through explicitly. |
| `--env XAUTHORITY="${XAUTHORITY}"` + `--bind "${XAUTHORITY}"` | X11 authentication cookie. If `$XAUTHORITY` is unset on your system (common with WSLg), skip both — WSLg's `$DISPLAY` typically doesn't need it. |

### NVIDIA GPU passthrough

If the machine has an NVIDIA GPU and you want napari using it instead of
software rendering, add `--nv`:

```bash
apptainer exec --nv \
    --bind /tmp/.X11-unix --env DISPLAY="${DISPLAY}" \
    container/PickMe.sif \
    PickMe choose_objects --input-dir /scratch/myuser/tomograms
```

`--nv` bind-mounts the host's NVIDIA driver libraries into the container so
OpenGL calls can reach the real GPU. Without it, the container falls back
to whatever software/virtual GL path the host provides (llvmpipe, WSLg's
virtual GPU, etc.) — often fine for clicking through a handful of objects,
just slower.

### Software-rendering fallback

If you hit "Could not create OpenGL context" (the same WSL failure mode
documented in `../docs/gui-setup.md`), force software rendering:

```bash
apptainer exec \
    --bind /tmp/.X11-unix --env DISPLAY="${DISPLAY}" \
    --env LIBGL_ALWAYS_SOFTWARE=1 \
    container/PickMe.sif \
    PickMe choose_objects --input-dir /scratch/myuser/tomograms
```

It's slower, but for picking a handful of objects that's a fine trade —
same advice as the non-container case.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `apptainer: command not found` on a cluster | No container runtime module loaded | `module load apptainer` (or your cluster's equivalent module name) |
| `FATAL: ... cannot build with the given definition (permission denied)` | No root, no `--fakeroot` | Build locally on your own Linux/WSL machine, then `scp` the `.sif` to the cluster — running a `.sif` never needs root |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | No `$DISPLAY`, or `/tmp/.X11-unix` wasn't bound | Confirm `echo $DISPLAY` is non-empty on the host *before* running apptainer; add `--bind /tmp/.X11-unix --env DISPLAY=$DISPLAY` |
| `choose_objects` hangs / no window ever appears, in an `sbatch` job | Batch/compute nodes have no display — this is a workflow constraint, not a bug (see `../docs/gui-setup.md` §2) | Run `choose_objects` in an interactive/X-forwarded session, never in `sbatch` |
| `Could not create OpenGL context` | GPU passthrough not giving Qt OpenGL 3.3 | `--env LIBGL_ALWAYS_SOFTWARE=1` |
| `EOFError` immediately, in a batch job | A subcommand prompted with `input()` and there's no terminal | Add `--non-interactive` (all subcommands except `particle_extraction`, which never prompts) |
| `X11 connection rejected because of wrong authentication` | `$XAUTHORITY` not passed through, or a stale cookie | Add `--env XAUTHORITY=$XAUTHORITY --bind $XAUTHORITY`; on WSLg try omitting `XAUTHORITY` entirely first |
| Build fails during the `%post` smoke-test step (`PickMe -h` etc.) | Something upstream in the build broke the install | Rebuild with `--sandbox` and `apptainer shell --writable` the sandbox to debug interactively |
| Data files "not found" inside the container despite existing on the host | Path isn't under `$HOME` or the launch directory, and wasn't bound | Add `--bind /path/on/host` (Apptainer only auto-binds `$HOME` and the current working directory) |
| **Docker:** the job runs fine but `outputs/` is nowhere on the host | Docker's working directory is `/opt/PickMe` inside the image, so `./outputs` was written into the container and destroyed with it | Add `-w /data` (a mounted path), or pass `--output-dir /data/outputs` |
| **Docker:** output files are owned by `root` and you need `sudo` to delete them | Docker runs as root unless told otherwise | Add `--user "$(id -u):$(id -g)"` |
| **Docker:** `bash: executable file not found` when asking for a shell | `ENTRYPOINT ["PickMe"]` means Docker tried to run `PickMe bash` | Add `--entrypoint bash` |
| **Docker:** prompts don't appear, or the command exits instantly | No TTY attached | Add `-it`, or pass `--non-interactive` |
| `conda: command not found` inside the container, or `conda activate` seems needed | You are probably not inside the container, or are in a `docker exec` shell that skipped the entry point | `which PickMe` should print `/opt/conda/envs/PickMe/bin/PickMe`. The environment is already on `PATH` — there is nothing to activate |

---

## What's inside

- Base image: `condaforge/miniforge3` (Ubuntu-based), pinned to a specific
  tag in `PickMe.def`/`Dockerfile` for reproducibility.
- The conda environment is built directly from `../PickMe.yml` — this
  directory does not maintain its own copy of the dependency list. If you
  change `PickMe.yml`, rebuild the image; you don't need to touch anything
  under `container/`.
- X11/OpenGL system libraries for Qt6, installed via `apt` (see comments in
  `PickMe.def` for the full list and why each is there).

## Files in this directory

| File | Purpose |
|---|---|
| `PickMe.def` | Apptainer/Singularity definition — the primary target, used on HPC |
| `Dockerfile` | Equivalent for local Docker/Podman builds; convert to `.sif` with `apptainer build ... docker-daemon://...` |
| `build.sh` | Builds `PickMe.sif` from `PickMe.def`; handles the no-root/`--fakeroot`/`--sandbox` cases |
| `README.md` | This file |
