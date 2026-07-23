# ShakeMap + Ground Failure — Workshop

## Launch

Go to this repo on GitHub → **Code** → **Codespaces** → **New codespace**. Wait ~60 seconds. The terminal opens in the ShakeMap environment — no activation needed.

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
