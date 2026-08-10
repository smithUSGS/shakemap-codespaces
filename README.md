# ShakeMap + Ground Failure — Workshop

## Getting started

1. Create a free GitHub account at https://github.com if you don't already have one
2. Go to this repo: [https://github.com/smithUSGS/shakemap-gf-workshop](https://github.com/smithUSGS/shakemap-gf-workshop)
3. Click the green **Code** button → **Codespaces** tab → **New with options**
4. Under **Region**, select **Europe West**, then click **Create codespace**
5. Wait about 60 seconds — a terminal will open automatically in the ShakeMap environment

A few things to know:
- Use your **personal** GitHub account — don't fork this repo (the pre-built image won't transfer)
- When you're done, stop the codespace: GitHub → Codespaces → **•••** → **Stop**
- If the connection is slow, try disconnecting from VPN or switching to a mobile hotspot

---

## Notebooks

Open the `data/notebooks/` folder in the Explorer and run cells top-to-bottom.
Select the **Python (ShakeMap)** kernel when prompted.

| Notebook | Description |
|---|---|
| `01_san_andreas_demo.ipynb` | Morning demo — M7.6 San Andreas scenario |
| `02_turkey_scenario.ipynb` | Afternoon hands-on — Turkey EAF scenario |

---

## Run ShakeMap

```bash
# Northridge M6.7 (California)
shake ci3144585 assemble -c "demo" model contour mapping gridxml

# Turkey M7.5
shake us6000jlqa assemble -c "demo" model contour mapping gridxml
```

View a map:
```bash
code ~/shakemap_profiles/default/data/ci3144585/current/products/intensity.jpg
```

---

## Run ground failure

Switch to the ground failure environment first:
```bash
conda activate gf
```

Run models for Turkey (type each command on one line):
```bash
gfailbin ~/groundfailure/defaultconfigfiles/models/jessee_2018_slim.ini ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml --gis

gfailbin ~/groundfailure/defaultconfigfiles/models/zhu_2017_general_slim.ini ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml --gis
```

Generate interactive map:
```bash
python ~/plot_gf_interactive.py
```

Download `turkey_gf.html` from the Explorer (right-click → Download) and open in a browser.

---

## Key paths

| | Path |
|---|---|
| ShakeMap outputs | `~/shakemap_profiles/default/data/<eventid>/current/products/` |
| Ground failure outputs | `~/gf_output/` |
| Model configs | `~/groundfailure/defaultconfigfiles/models/` |
| Turkey GF inputs | `~/turkey_inputs/` |

## Switch environments

```bash
conda activate shakemap   # ShakeMap (default on launch)
conda activate gf         # groundfailure tools
```
