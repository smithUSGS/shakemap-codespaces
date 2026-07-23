# ShakeMap and Ground Failure — Workshop

## Getting started

Here's how to get started with the workshop environment:

1. Create a free GitHub account at https://github.com if you don't already have one
2. Go to this repo: https://github.com/smithUSGS/shakemap-codespaces
3. Click the green Code button → Codespaces tab → New codespace
4. Wait about 60 seconds for it to load — a terminal will open automatically
5. See the README for some example commands you can run

A few things to know:
- Use your own personal GitHub account (the environment runs on your free quota at no cost to you)
- Launch directly from this repository — don’t fork it, as that won’t have the pre-built image
- When you’re done, stop the codespace via GitHub → Codespaces → ••• → Stop
  
## Run ShakeMap

```bash
# Northridge (California)
shake ci3144585 assemble -c "demo" model contour mapping

# Turkey M7.5
shake us6000jlqa assemble -c "demo" model contour mapping
```

View a map:
```bash
code ~/shakemap_profiles/default/data/ci3144585/current/products/intensity.jpg
```

## Run ground failure

```bash
conda activate gf

# Turkey — Jessee 2018 landslide + Zhu 2017 liquefaction
gfailbin ~/groundfailure/defaultconfigfiles/models/jessee_2018_slim.ini \
  ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml --gis

gfailbin ~/groundfailure/defaultconfigfiles/models/zhu_2017_general_slim.ini \
  ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml --gis

# Interactive two-panel map
python ~/plot_gf_interactive.py
```

Download `turkey_gf.html` from the Explorer (right-click → Download) and open in a browser.

## Key paths

| | Path |
|---|---|
| ShakeMap outputs | `~/shakemap_profiles/default/data/<eventid>/current/products/` |
| Ground failure outputs | `~/gf_output/` |
| Model configs | `~/groundfailure/defaultconfigfiles/models/` |

## Switch environments

```bash
conda activate shakemap   # ShakeMap (default)
conda activate gf         # groundfailure
```

## Stop the codespace

GitHub → Codespaces → **•••** → **Stop codespace** when done.
