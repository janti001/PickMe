# Installing PickMe and Getting the GUI to Open a Window

`choose_objects` opens a napari viewer so you can *see* your segmentations and
click the objects you want. That is the point of PickMe, and it is a
first-class, default-installed feature — nothing here is optional.

But getting it working has two separate halves, and they fail for completely
different reasons:

1. **Installing the packages.** Solved by pinning and by using conda-forge.
2. **Having a window system to draw into.** No amount of pinning fixes a
   machine with no display. This is where WSL and HPC bite.

Work through them in that order.

---

## 1. Installing: use conda, not pip

**conda-forge is the only supported install path for the GUI.**

```bash
conda env create -f PickMe.yml
conda activate pickme
```

That is it. `PickMe.yml` installs the package itself with `pip --no-deps` on
purpose, so pip cannot reach in and swap out the Qt libraries conda just
installed.

### Why not `pip install PickMe-EM`?

pip will work, and it is fine if you are scripting the non-GUI stages. But
napari sits on Qt, and Qt is a large pile of compiled C++ libraries. When pip
and conda both provide those libraries, you can end up with a Python binding
built against one Qt and a Qt runtime from another. The symptom is not a clean
error — it is a segfault, or a window that never appears, or a plugin that
loads but shows nothing.

If you install with pip, install into an environment with no conda-provided Qt.
Do not mix.

### What is pinned, and why

`pyproject.toml` and `PickMe.yml` pin the GUI stack much more tightly than
everything else:

| Package | Pin |
|---|---|
| `napari` | `>=0.7.0,<0.8` |
| `napari-skimage` | `>=0.6.0,<0.7` |
| `pyqt6` | `>=6.9,<6.12` |
| `qt6-main` (conda only) | `>=6.9,<6.12` |

The tight pin on `napari-skimage` is not caution for its own sake.
`choose_objects` drives the Regionprops widget by searching its Qt widget tree
for the results table and the Run button, because the plugin exposes no API for
this. A minor release that renames or reorders a widget breaks object selection
*silently* — you get an empty selection rather than an error.

All of that private-API access is isolated in
`src/PickMe/gui/napari_compat.py`. Before the viewer opens, PickMe checks the
installed versions against the pins and warns if they disagree:

```
[PickMe] WARNING: expected napari-skimage >=0.6.0,<0.7, found 0.7.0 — GUI
selection may not work. See docs/gui-setup.md for the supported install path.
```

If you see that, you have an unpinned environment. Recreate it from
`PickMe.yml`.

**If you change a pin, change it in all three places:** `pyproject.toml`,
`PickMe.yml`, and `SUPPORTED_VERSIONS` in `src/PickMe/gui/napari_compat.py`.

### A note on the X11 libraries

`PickMe.yml` deliberately does *not* list `xcb-util*` or `libxkbcommon`.
conda-forge only ships those for Linux, so naming them directly makes the
environment file unsolvable on macOS. `qt6-main` already pulls in the correct
set for whichever platform you are installing on.

---

## 2. Getting a window: platform by platform

A successful install does not mean a window will appear. Qt needs a display
server. Here is what each platform needs.

### Linux desktop

Works out of the box. Nothing to do.

### WSL (Windows Subsystem for Linux)

You need one of:

- **WSLg** — built into Windows 11 and recent Windows 10 builds. If you have
  it, GUI apps just work. Check with `echo $DISPLAY`; if it prints something
  like `:0`, you are set.
- **An X server on the Windows side** — VcXsrv or X410 — for older Windows 10.
  Start it, allow it through the Windows firewall, then in WSL:

  ```bash
  export DISPLAY=$(ip route list default | awk '{print $3}'):0
  ```

If napari starts but crashes complaining about OpenGL — typically "Could not
create OpenGL context" or a request for OpenGL 3.3 — WSL's GPU passthrough is
not giving Qt what it needs. Fall back to software rendering:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
PickMe choose_objects --input-dir /path/to/tomograms
```

It is slower, but it works, and for clicking a handful of objects that is a
perfectly good trade.

### HPC clusters

This is the important one, and it is a **workflow constraint, not a bug**.

**A batch job cannot run `choose_objects`.** When you `sbatch` a script, the
compute node it lands on has no display attached, and there is no way to give
it one from inside the job. This is true no matter how the packages were
installed.

You have three options:

1. **`ssh -X` or `ssh -Y` to a login node**, then run `choose_objects`
   directly. Fine for a few tomograms; X forwarding over a slow link makes
   napari painful for many.
2. **An interactive job with X forwarding**, e.g.
   `srun --pty --x11 /bin/bash`, or a VNC / remote-desktop session if your
   cluster provides one. Better than a login node because you get real
   resources.
3. **Split the work** — the option that scales best:

   | Stage | Where |
   |---|---|
   | `filter_objects` | Cluster, batch |
   | `choose_objects` | Your own machine, or an interactive/X-forwarded session |
   | `particle_extraction` | Cluster, batch |

   Run the heavy compute on the cluster, sync `outputs/` down to your laptop,
   pick objects locally with a real display, then sync the `choose/jobNNN`
   directory back up and carry on.

If PickMe cannot find a display it says so before napari has a chance to
produce a cryptic Qt error:

```
[PickMe] WARNING: no DISPLAY or WAYLAND_DISPLAY is set, so Qt has no window
system to draw into. On HPC, connect with `ssh -X`/`-Y` or use an interactive
job or VNC session — batch (sbatch) jobs cannot run choose_objects.
```

---

## 3. Running the non-GUI stages unattended

`filter_objects`, `choose_objects`, `decompress` and `convert` all ask
questions with `input()`. Under a batch scheduler there is no terminal to
answer them, so `input()` raises `EOFError` and the job dies before doing any
work — a separate problem from the GUI, with the same "works on my laptop"
shape.

Pass `--non-interactive` to skip every prompt and take the default:

| Subcommand | What `--non-interactive` assumes |
|---|---|
| `filter_objects` | Process every segmentation file found |
| `choose_objects` | Do not open napari; take the "no selection" path |
| `decompress` | Decompress every file found |
| `convert` | Convert every `.mrc` file found |

`particle_extraction` never prompts, so it needs no flag.

A batch script for the two heavy stages:

```bash
#!/bin/bash
#SBATCH --job-name=pickme
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G

source activate pickme

PickMe filter_objects --input-dir /scratch/$USER/segmentations --non-interactive
PickMe particle_extraction --sample-rate 20
```

Then pick objects interactively, somewhere with a display, in between.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `EOFError` immediately on start, in a batch job | A prompt with no terminal to read from | Add `--non-interactive` |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | No display, or missing X libraries | Section 2 — check `$DISPLAY`; on HPC use `ssh -X` or an interactive job |
| Window opens, then segfaults | Mixed pip and conda Qt | Recreate the environment from `PickMe.yml` |
| "Could not create OpenGL context" on WSL | GPU passthrough not giving Qt OpenGL 3.3 | `export LIBGL_ALWAYS_SOFTWARE=1` |
| `[PickMe] WARNING: expected napari-skimage ...` | Unpinned environment | Recreate from `PickMe.yml` |
| Viewer opens, you click rows, nothing is selected | napari-skimage moved its widgets | Check the version against the pins above; the shim lives in `src/PickMe/gui/napari_compat.py` |
| `[PickMe] Could not find regionprops table` | Run/Analyse not clicked yet, or a version mismatch | Click Run in the widget first; if it persists, check versions |

---

## Related

- `docs/known-issues.md` — catalogued bugs
- `docs/deployment-plan.md` — the full cross-platform plan this document is
  part of (Plan A)
- `docs/cli-reference.md` — every subcommand and flag
