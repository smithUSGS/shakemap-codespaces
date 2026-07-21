# ShakeMap + Ground Failure — Workshop

This repository contains a pre-configured environment for running **USGS ShakeMap v4.4.9** and **groundfailure** in a browser, with no local installation required.

---

## Launching the environment

1. Go to this repository on GitHub
2. Click the green **Code** button → **Codespaces** tab → **New codespace**
3. Wait about 30–60 seconds for the environment to load (it's pulling a pre-built image)
4. A terminal opens automatically — you're ready to go

> **Note:** The terminal prompt shows `(shakemap)` — this means the ShakeMap environment is active. You don't need to activate anything.

---

## What's already installed and ready

Everything is pre-installed and pre-staged. No downloads happen when you launch.

| Component | Details |
|---|---|
| ShakeMap | v4.4.9, with global Vs30 and topography grids baked in |
| groundfailure | Jessee 2018 (landslide) + Zhu 2017 (liquefaction) |
| Demo event — US | `ci3144585` — 1994 Northridge M6.7, California |
| Demo event — Turkey | `us6000jlqa` — 2023 Kahramanmaraş M7.5, Turkey |
| Input data | All groundfailure input layers for Turkey pre-staged |
| Plotting scripts | `~/plot_gf.py` (static) and `~/plot_gf_interactive.py` (interactive map) |

---

## Running ShakeMap

Both demo events are pre-staged — just run the pipeline directly.

### Northridge (California)

```bash
shake ci3144585 assemble -c "demo" model contour mapping
```

### Turkey M7.5

```bash
shake us6000jlqa assemble -c "demo" model contour mapping
```

The `model` step takes about 1–2 minutes. When it finishes you'll see `shake finished`.

### Viewing ShakeMap outputs

Products land in `~/shakemap_profiles/default/data/<eventid>/current/products/`.
Open a map image directly in VS Code:

```bash
code ~/shakemap_profiles/default/data/ci3144585/current/products/intensity.jpg
code ~/shakemap_profiles/default/data/us6000jlqa/current/products/intensity.jpg
```

---

## Running ground failure

Ground failure reads the ShakeMap grid and estimates landslide and liquefaction probability. Switch to the `gf` environment first:

```bash
conda activate gf
```

### Northridge — static 3-panel map (Godt, Nowicki, Zhu)

```bash
python ~/plot_gf.py \
  --shakefile ~/shakemap_profiles/default/data/ci3144585/current/products/grid.xml \
  --datadir ~/groundfailure/notebooks/data/model_inputs/northridge \
  --outfile ~/northridge_gf.png
```

Download `northridge_gf.png` via the Explorer (right-click → Download) and open it in your browser.

### Turkey — run models via gfailbin

```bash
# Jessee 2018 landslide
gfailbin ~/groundfailure/defaultconfigfiles/models/jessee_2018_slim.ini \
  ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \
  --gis

# Zhu 2017 liquefaction
gfailbin ~/groundfailure/defaultconfigfiles/models/zhu_2017_general_slim.ini \
  ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \
  --gis
```

Outputs go to `~/gf_output/us6000jlqa/`.

### Turkey — interactive two-panel HTML map

```bash
python ~/plot_gf_interactive.py \
  --ls-model "Nowicki Jessee (2018):$HOME/gf_output/us6000jlqa/us6000jlqa_jessee_2018_slim_model.tif:$HOME/groundfailure/defaultconfigfiles/models/jessee_2018_slim.ini" \
  --lq-model "Zhu and others (2017):$HOME/gf_output/us6000jlqa/us6000jlqa_zhu_2017_general_slim_model.tif:$HOME/groundfailure/defaultconfigfiles/models/zhu_2017_general_slim.ini" \
  --shakefile $HOME/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \
  --contours $HOME/shakemap_profiles/default/data/us6000jlqa/current/products/cont_mmi.json \
  --outfile ~/turkey_gf.html
```

Download `turkey_gf.html` (right-click in Explorer → Download) and open it in your browser. You'll see landslide and liquefaction maps side by side with a stats table.

---

## Finding your output files

Output files land **outside** the repo folder, so they don't appear in the Explorer sidebar by default. Two ways to access them:

**Option 1 — open a file directly from the terminal:**
```bash
code ~/northridge_gf.png
```

**Option 2 — add the outputs folder to the Explorer:**
File → Add Folder to Workspace → type `/home/vscode` → Add

---

## Switching between environments

| Environment | What it runs | How to switch |
|---|---|---|
| `shakemap` | ShakeMap pipeline (`shake`, `sm_create`, etc.) | Default on launch |
| `gf` | groundfailure (`gfailbin`, plotting scripts) | `conda activate gf` |

To switch back to ShakeMap:
```bash
conda activate shakemap
```

---

## Stopping the codespace

When you're done, **stop** the codespace rather than just closing the browser tab — this prevents compute charges while preserving your work.

GitHub → Codespaces → find your codespace → **•••** → **Stop codespace**

Your files are saved automatically and will be there when you resume.

---

## Key file locations

| Item | Path |
|---|---|
| ShakeMap profile / data | `~/shakemap_profiles/default/data/` |
| ShakeMap grids (Vs30, topo) | `~/shakemap_data/` |
| groundfailure repo | `~/groundfailure/` |
| Model configs | `~/groundfailure/defaultconfigfiles/models/` |
| Turkey input layers | `~/turkey_inputs/` |
| Ground failure outputs | `~/gf_output/` |
| Static plot script | `~/plot_gf.py` |
| Interactive map script | `~/plot_gf_interactive.py` |
