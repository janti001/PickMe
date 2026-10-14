# Installing PickMe and Getting the GUI to Open a Window

`choose_objects` opens a napari viewer so you can *see* your segmentations and
click the objects you want. That is the point of PickMe, and it is a
first-class, default-installed feature on the conda path.

But getting it working has two separate halves, and they fail for completely
different reasons:

1. **Installing the packages.** Solved by version ranges and by using conda-forge.
2. **Having a window system to draw into.** No amount of pinning fixes a
   machine with no display. This is where WSL and HPC bite.

Work through them in that order.

---

## 1. Installing: use conda, not pip

**conda-forge is the only supported install path for the GUI.**

```bash
conda env create -f PickMe.yml
conda activate PickMe
```

That is it. `PickMe.yml` installs the package itself with `pip --no-deps` on
purpose, so pip cannot reach in and swap out the Qt libraries conda just
installed.

### The container is the other supported path

If conda has failed you — most likely on an HPC cluster, where the solver
crawls on a shared filesystem and you have no root — skip conda entirely and
use the container. It ships the whole stack, including the X11/OpenGL
libraries, already solved:

```bash
apptainer exec container/PickMe.sif PickMe -h
```

See [`../container/README.md`](../container/README.md) for building the image,
starting a container, and working inside one.

### Why not `pip install PickMe-EM`?

pip will work, and it is fine if you are scripting the non-GUI stages. But
napari sits on Qt, and Qt is a large pile of compiled C++ libraries. When pip
and conda both provide those libraries, you can end up with a Python binding
built against one Qt and a Qt runtime from another. The symptom is not a clean
error — it is a segfault, or a window that never appears, or a plugin that
loads but shows nothing.

If you install with pip, install into an environment with no conda-provided Qt.
Do not mix.

**The GUI stack is an optional extra for pip installs**, so a headless machine
never has to resolve napari or Qt at all:

```bash
pip install PickMe-EM                # headless: filter_objects, particle_extraction,
                                     # decompress, convert. No napari, no Qt, no OpenGL
pip install "PickMe-EM[gui]"         # adds napari, qtpy, PyQt6, vispy
pip install "PickMe-EM[gui-pyqt5]"   # same, but with PyQt5 (see section 2)
```

Install **one** of the two GUI extras, never both. This is deliberate: resolving
an OpenGL stack a compute node can never use was a significant part of what made
cluster installs slow and fragile. The conda path is unaffected — `PickMe.yml`
installs the GUI packages directly, so the GUI remains default-installed there.

If you install without a GUI extra and then answer "yes" at the object-selection
prompt, PickMe tells you exactly what to install rather than raising a bare
`ModuleNotFoundError`.

### What is pinned, and why

`pyproject.toml` and `PickMe.yml` pin the GUI stack much more tightly than
everything else:

| Package | Pin |
|---|---|
| `napari` | `>=0.7.0,<0.8` |
| `vispy` | `>=0.16.1,<0.17` |
| `pyqt6` (default) | `>=6.9,<6.12` |
| `qt6-main` (conda only) | `>=6.9,<6.12` |
| `PyQt5` (Qt5 variant) | `5.15.x` |

PickMe reaches into a few napari/vispy internals (the object picker's mouse
handling, and the viewer clean-up in `src/PickMe/gui/napari_compat.py`), so an
unconstrained minor upgrade can break the viewer. Before the viewer opens,
PickMe checks the installed versions against the pins and warns if they
disagree. If you see that warning, you have an unpinned environment — recreate
it from `PickMe.yml` (or `PickMe-pyqt5.yml`).

**If you change a pin, change it in all three places:** `pyproject.toml`, the
conda `.yml` file(s), and `SUPPORTED_VERSIONS` in
`src/PickMe/gui/napari_compat.py`.

### A note on the X11 libraries

`PickMe.yml` deliberately does *not* list `xcb-util*` or `libxkbcommon`.
conda-forge only ships those for Linux, so naming them directly makes the
environment file unsolvable on macOS. `qt6-main` already pulls in the correct
set for whichever platform you are installing on.

---

## 2. PyQt6 or PyQt5?

napari draws its window with Qt, and Qt comes in two generations. PickMe
supports both, but they are separate installs.

| | PyQt6 (default) | PyQt5 |
|---|---|---|
| conda | `PickMe.yml` | `PickMe-pyqt5.yml` |
| pip | `pip install "PickMe-EM[gui]"` | `pip install "PickMe-EM[gui-pyqt5]"` |
| Environment name | `PickMe` | `PickMe-pyqt5` |
| Use when | Laptops, workstations, almost everything | Old Linux/HPC systems whose admin requires Qt5 |

**Use PyQt6 unless you have been told otherwise.** The Qt5 variant exists only
for clusters where the sysadmin will not allow Qt6 (typically very old
operating systems). Everything except the Qt binding is identical between the
two, and the two environments can live side by side on one machine because
they have different names.

```bash
conda env create -f PickMe-pyqt5.yml
conda activate PickMe-pyqt5
```

### What `QT_API` does

All of PickMe's Qt code goes through `qtpy`, a thin layer that uses whichever
Qt binding it finds. The environment variable `QT_API` tells it which one to
use. `PickMe-pyqt5.yml` sets `QT_API=pyqt5` for you: conda sets it when you
`conda activate PickMe-pyqt5` and removes it on deactivate. You do not need to
set it yourself in the conda environment.

This matters because conda's `napari` package also pulls in PySide6 (another
Qt6 binding), so that environment holds more than one binding. Without
`QT_API`, qtpy would pick on its own; with it, the choice is explicit.

### Do not mix bindings

- In a **pip** environment, install exactly one of `[gui]` or `[gui-pyqt5]`.
  If both PyQt5 and PyQt6 are present, qtpy picks **PyQt5**, which may not be
  what you meant.
- If you do end up with both and need to force the choice, set `QT_API`
  (`pyqt6` or `pyqt5`) before running PickMe.
- Do not install a Qt binding with pip into a conda environment that already
  has one (see section 1).

---

## 3. Getting a window: platform by platform

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

#### 3D volume view crashes

If the viewer opens and 2D slice viewing works, but toggling to **3D** in
napari crashes with a long traceback ending in something like:

```
RuntimeError: Cannot SIZE object 44 because it does not exist
```

napari will report this as a "version mismatch between vispy and napari."
It usually is not. 3D volume rendering pushes far more through OpenGL than
2D slice viewing - a large 3D texture and an active shader - and a software
rasterizer (`llvmpipe`/`softpipe`/`swrast`, which is exactly what
`LIBGL_ALWAYS_SOFTWARE=1` above gives you, or whatever WSL's GPU passthrough
falls back to when it can't do better) can handle 2D fine and then fail
partway through building the 3D texture. PickMe prints a warning right after
the viewer opens if it detects this:

```
[PickMe] WARNING: napari's OpenGL renderer is 'llvmpipe (...)', a software
(CPU) rasterizer rather than a GPU. 2D slice viewing is fine, but toggling to
3D is known to crash software rasterizers ...
```

There is no software fix for a software rasterizer's 3D texture limits.
Options:

- Stick to 2D slice viewing for object selection - it does not need 3D.
- Get real GPU passthrough working for WSL (recent WSLg + up-to-date GPU
  drivers on the Windows side), so Qt does not fall back to
  `LIBGL_ALWAYS_SOFTWARE`.
- Run `choose_objects` on a machine with a real GPU instead (see the HPC
  workflow split below - the same idea applies to any machine without one).

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

## 4. Picking objects in the viewer

`choose_objects` shows **one tomogram at a time**, with its segmentation drawn
on top. Objects are selected by clicking them.

- **Click** an object to select it; click it again to deselect it. This works
  in both the 2D slice view and the 3D view.
- **Drag** to pan (2D) or rotate (3D). A drag never changes the selection — a
  press-and-release that moves more than a few pixels counts as a drag, not a
  click.
- Only the left mouse button selects, and only in napari's normal navigation
  mode (not while the paint, fill or erase tools are active).
- **Colours:** selected objects are bright **green**; unselected objects are
  **magenta**; background is transparent.
- The viewer opens on the middle of the z-slices that contain objects.

The **PickMe objects** panel on the right of the window shows:

- a tomogram drop-down with **Previous** / **Next** buttons for moving between
  tomograms. Selections are remembered per tomogram while you switch, and the
  previous tomogram is unloaded, so memory stays at about one tomogram.
- the list of selected objects (for example `label 12 — 48,301 voxels`), with
  **Remove selected** and **Clear all**.
- a status line.

If a tomogram's segmentation has a different shape, or the file is corrupt,
PickMe warns and returns you to the previous tomogram.

**Close the napari window to finish** — closing it is what writes the output
(`outputs/choose/jobNNN/`). Tomograms with nothing selected are skipped; if
nothing is selected anywhere, no files are written.

---

## 5. Running the non-GUI stages unattended

`filter_objects`, `choose_objects`, `decompress` and `convert` all ask
questions with `input()`. Under a batch scheduler there is no terminal to
answer them, so `input()` raises `EOFError` and the job dies before doing any
work — a separate problem from the GUI, with the same "works on my laptop"
shape.

Pass `--non-interactive` to skip every prompt and take the default:

| Subcommand | What `--non-interactive` assumes |
|---|---|
| `filter_objects` | Process every segmentation file found |
| `choose_objects` | Cancels the job (object picking needs a display); nothing is written |
| `decompress` | Decompress every file found |
| `convert` | Convert every `.mrc` file found |

`particle_extraction` never prompts, so it needs no flag.

A batch script for the two heavy stages:

```bash
#!/bin/bash
#SBATCH --job-name=pickme
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G

conda activate PickMe

PickMe filter_objects --input-dir /scratch/$USER/segmentations --non-interactive
PickMe particle_extraction --sample-rate 20
```

Then pick objects interactively, somewhere with a display, in between.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `EOFError` immediately on start, in a batch job | A prompt with no terminal to read from | Add `--non-interactive` |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | No display, or missing X libraries | Section 3 — check `$DISPLAY`; on HPC use `ssh -X` or an interactive job |
| Window opens, then segfaults | Mixed pip and conda Qt, or two Qt bindings fighting | Recreate the environment from `PickMe.yml` (or `PickMe-pyqt5.yml`); see section 2 |
| "Could not create OpenGL context" on WSL | GPU passthrough not giving Qt OpenGL 3.3 | `export LIBGL_ALWAYS_SOFTWARE=1` |
| Viewer opens and 2D works, but toggling to 3D crashes with `Cannot SIZE object ... does not exist` | Software OpenGL rasterizer (e.g. `llvmpipe`) failing on a 3D volume texture, not a version mismatch | See [3D volume view crashes](#3d-volume-view-crashes) above - stick to 2D, or get real GPU passthrough |
| `[PickMe] WARNING: expected napari ...` (or vispy) | Unpinned environment | Recreate from `PickMe.yml` / `PickMe-pyqt5.yml` |
| Clicking an object does nothing | Paint/fill/erase tool active, or a right/middle click | Switch the labels layer to normal navigation mode and use the left button |
| Wrong Qt binding in use (PyQt5 when you wanted PyQt6) | Both bindings installed in one pip env | Install only one GUI extra, or set `QT_API=pyqt6` |

---

## Related

- `docs/known-issues.md` — catalogued bugs
- `docs/deployment-plan.md` — the full cross-platform plan this document is
  part of (Plan A)
- `docs/cli-reference.md` — every subcommand and flag
