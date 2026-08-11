#!/usr/bin/env bash
# build.sh — build the PickMe-EM Apptainer/Singularity image (PickMe.sif).
#
# Usage:
#   ./container/build.sh                  # normal build, output: container/PickMe.sif
#   ./container/build.sh --fakeroot       # build without real root (see notes below)
#   ./container/build.sh --sandbox        # build a debuggable directory instead of a .sif
#   ./container/build.sh --fakeroot out.sif   # custom output path, in any order
#
# Run this script from anywhere — it cds to the repo root itself, which
# matters because container/PickMe.def's %files paths are resolved relative
# to the directory `apptainer build` is run FROM, not relative to the .def
# file. See the comment at the top of container/PickMe.def.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." &>/dev/null && pwd)"
DEF_FILE="container/PickMe.def"
OUT_PATH="container/PickMe.sif"
FAKEROOT=0
SANDBOX=0

# --- Parse args --------------------------------------------------------
for arg in "$@"; do
    case "${arg}" in
        --fakeroot)
            FAKEROOT=1
            ;;
        --sandbox)
            SANDBOX=1
            OUT_PATH="container/PickMe.sandbox"
            ;;
        -h|--help)
            sed -n '2,15p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *)
            # Anything else is treated as a custom output path.
            OUT_PATH="${arg}"
            ;;
    esac
done

# --- Pick a builder ------------------------------------------------------
# Apptainer is the current name of the project; Singularity (SingularityCE)
# is the same tool under its older name and is still common on HPC. Prefer
# whichever is on PATH, apptainer first.
if command -v apptainer &>/dev/null; then
    BUILDER=apptainer
elif command -v singularity &>/dev/null; then
    BUILDER=singularity
else
    echo "ERROR: neither 'apptainer' nor 'singularity' is on PATH." >&2
    echo "" >&2
    echo "This is expected on a plain HPC login node without a container" >&2
    echo "runtime module loaded — try 'module load apptainer' (or similar)" >&2
    echo "first. If it's genuinely unavailable, build on a machine that has" >&2
    echo "it (your own Linux box, or via Docker + conversion — see README.md" >&2
    echo "'Building the image' section) and copy the resulting PickMe.sif" >&2
    echo "over with scp/rsync; running a prebuilt .sif needs no build tools" >&2
    echo "at all." >&2
    exit 1
fi

# --- Root / fakeroot notes ------------------------------------------------
# A normal `apptainer build` of a .sif needs either real root or the
# --fakeroot feature. On shared HPC login nodes you almost never have real
# root, and --fakeroot only works if a cluster admin has configured
# /etc/subuid + /etc/subgid entries for your account. If neither is true:
#   - Build on your own Linux machine (or a Linux VM/WSL) where you do have
#     root or a working --fakeroot, then scp/rsync the .sif to the cluster.
#   - Or ask your HPC admin to run the build, or to enable --fakeroot for
#     your account.
# --sandbox (a plain directory instead of a squashfs .sif) is useful while
# iterating on PickMe.def, since `apptainer build --sandbox` is faster to
# rebuild and `apptainer shell --writable sandbox/` lets you poke around
# and debug a failed %post step interactively.
BUILD_ARGS=(build)
if [[ "${FAKEROOT}" -eq 1 ]]; then
    BUILD_ARGS+=(--fakeroot)
fi
if [[ "${SANDBOX}" -eq 1 ]]; then
    BUILD_ARGS+=(--sandbox)
fi
BUILD_ARGS+=("${OUT_PATH}" "${DEF_FILE}")

echo "Building with: ${BUILDER} ${BUILD_ARGS[*]}"
echo "Working directory: ${REPO_ROOT}"
cd "${REPO_ROOT}"

"${BUILDER}" "${BUILD_ARGS[@]}"

echo ""
echo "Build complete: ${REPO_ROOT}/${OUT_PATH}"
if [[ "${SANDBOX}" -eq 0 ]]; then
    echo "Sanity check:  ${BUILDER} test ${OUT_PATH}"
    echo "Run it:        ${BUILDER} run ${OUT_PATH} -h"
fi
