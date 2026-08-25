#!/usr/bin/env python3
"""
plot_gf_interactive.py — interactive HTML map of groundfailure model output(s).

Usage (single model):
    python plot_gf_interactive.py --tif <model.tif> --outfile <output.html>
                                  [--title "My map title"]
                                  [--config  path/to/model.ini]
                                  [--shakefile path/to/grid.xml]
                                  [--rupture  path/to/rupture.json]
                                  [--contours path/to/cont_mmi.json]
                                  [--threshold 0.002]

Usage (multi-model layer switch):
    python plot_gf_interactive.py --outfile <output.html> \\
        --model "LABEL:TIF:CONFIG" [--model "LABEL:TIF:CONFIG" ...] \\
        [--shakefile path/to/grid.xml] [--rupture path/to/rupture.json] \\
        [--contours path/to/cont_mmi.json]

    --model format: "LABEL:TIF:CONFIG"
    e.g. "Nowicki Jessee (2018):~/gf/jessee_model.tif:~/cfg/jessee_2018_slim.ini"
    Repeat --model 2-3 times to build a layer-switchable map.

Other arguments:
    --shakefile  ShakeMap grid.xml -- adds epicenter marker
    --rupture    rupture.json -- adds finite fault trace overlay
    --contours   ShakeMap contour GeoJSON (e.g. cont_mmi.json)
    --threshold  Mask values below this (default: from config or 0.002)

Example (multi-model, Turkey):
    python plot_gf_interactive.py \\
        --model "Nowicki Jessee (2018):~/gf_turkey/us6000jlqa/us6000jlqa_jessee_2018_slim_model.tif:~/groundfailure/defaultconfigfiles/models/jessee_2018_slim.ini" \\
        --model "Zhu and others (2017):~/gf_turkey/us6000jlqa/us6000jlqa_zhu_2017_general_slim_model.tif:~/groundfailure/defaultconfigfiles/models/zhu_2017_general_slim.ini" \\
        --shakefile ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \\
        --rupture ~/shakemap_profiles/default/data/us6000jlqa/current/products/rupture.json \\
        --contours ~/shakemap_profiles/default/data/us6000jlqa/current/products/cont_mmi.json \\
        --outfile ~/turkey_gf_map.html
"""

import argparse
import json
import io
import base64
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import rasterio
import rasterio.warp
import folium


def read_config(config_path):
    try:
        from configobj import ConfigObj
        cfg = ConfigObj(config_path)
        model_name = list(cfg.keys())[0]
        disp = cfg[model_name].get("display_options", {})
        lims_val = disp.get("lims", {}).get("model", None)
        thresh_val = disp.get("maskthresholds", {}).get("model", None)
        cmap_str = disp.get("colors", {}).get("model", None)

        # ConfigObj auto-parses comma-separated values into a list, so
        # handle both list (normal) and string (defensive) forms.
        if isinstance(lims_val, list):
            bins = [float(x) for x in lims_val] if lims_val else None
        elif lims_val and lims_val != "None":
            bins = [float(x.strip()) for x in lims_val.split(",")]
        else:
            bins = None

        if isinstance(thresh_val, list):
            threshold = float(thresh_val[0]) if thresh_val else None
        elif thresh_val and thresh_val != "None":
            threshold = float(thresh_val)
        else:
            threshold = None

        cmap = cmap_str.replace("cm.", "") if cmap_str and cmap_str != "None" else None
        return bins, threshold, cmap
    except Exception:
        return None, None, None


def get_epicenter(shakefile):
    try:
        ns = {"sm": "http://earthquake.usgs.gov/eqcenter/shakemap"}
        root = ET.parse(shakefile).getroot()
        ev = root.find("sm:event", ns).attrib
        return (float(ev["lat"]), float(ev["lon"]),
                float(ev.get("magnitude", 0)),
                ev.get("event_description", ""))
    except Exception:
        return None, None, None, ""


def tif_to_png_overlay(tif_path, cmap_name, bins, threshold):
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
        bounds_src = src.bounds
        crs = src.crs
        if crs.to_epsg() != 4326:
            bounds_wgs84 = rasterio.warp.transform_bounds(
                crs, "EPSG:4326",
                bounds_src.left, bounds_src.bottom,
                bounds_src.right, bounds_src.top)
        else:
            bounds_wgs84 = (bounds_src.left, bounds_src.bottom,
                            bounds_src.right, bounds_src.top)

    if nodata is not None:
        data[data == nodata] = np.nan
    data[data < threshold] = np.nan

    cmap = plt.get_cmap(cmap_name)
    if bins is not None:
        norm = mcolors.BoundaryNorm(bins, cmap.N)
        vmin, vmax = bins[0], bins[-1]
    else:
        vmin = float(np.nanpercentile(data, 2))
        vmax = float(np.nanpercentile(data, 98))
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    rgba = cmap(norm(data))
    rgba[..., 3] = np.where(np.isnan(data), 0, 0.65)

    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_b64, bounds_wgs84, vmin, vmax, norm, cmap, rgba


# groundfailure's own legend renderer + default palette/bins — imported
# directly so the legend is pixel-identical to the official USGS
# ground-failure product legend, and stays in sync automatically if
# groundfailure changes its palette.
try:
    from gfail.webpage import make_legend as _gf_make_legend
    from gfail.webpage import DFCOLORS as _GF_DFCOLORS
    from gfail.webpage import DFBINS as _GF_DFBINS
    _HAVE_GF_LEGEND = True
except Exception:
    _HAVE_GF_LEGEND = False


def make_colorbar(cmap, norm, bins, title):
    """Legend strip matching the official groundfailure product legend.

    Uses gfail.webpage.make_legend with the DFCOLORS/DFBINS defaults
    whenever the model's own bins match the default 7-edge scheme (the
    normal case for jessee_2018 / zhu_2017 / allstadt-style configs), so
    every panel that shares the default bins renders an identical legend.
    Falls back to a continuous matplotlib colorbar if groundfailure isn't
    importable or the model defines a non-default number of bins.
    """
    use_default = (
        _HAVE_GF_LEGEND and bins is not None and len(bins) == len(_GF_DFBINS)
    )
    if use_default:
        import copy as _copy
        plt.close("all")  # make sure we grab only this call's figure
        _gf_make_legend(
            _copy.deepcopy(_GF_DFBINS),
            _copy.deepcopy(_GF_DFCOLORS),
            filename=None,
            orientation="horizontal",
            title=title,
            transparent=False,
        )
        fig = plt.gcf()  # make_legend builds but does not return the figure
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", transparent=False, dpi=150)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)
        return b64

    # fall back to a continuous bar if groundfailure's legend isn't usable
    fig, ax = plt.subplots(figsize=(4, 0.4))
    fig.subplots_adjust(bottom=0.5)
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap),
                      cax=ax, orientation="horizontal")
    if bins is not None:
        cb.set_ticks(bins)
        cb.set_ticklabels([str(b) for b in bins])
    cb.set_label(title, fontsize=9)
    ax.tick_params(labelsize=7)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=False, dpi=120)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return b64


def panel_stats(tif_path, threshold):
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    valid = data[~np.isnan(data)]
    if len(valid) == 0:
        return 0.0, 0.0
    above = float(np.sum(data > threshold))
    return float(np.nanmax(data)), 100.0 * above / len(valid)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive HTML map of groundfailure model output(s).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument("--tif", default=None,
                        help="Single-model mode. Ignored if --model is given.")
    parser.add_argument("--outfile", default="groundfailure_map.html")
    parser.add_argument("--title", default="Ground Failure Model")
    parser.add_argument("--config", default=None,
                        help="Single-model mode. Ignored if --model is given.")
    parser.add_argument("--model", action="append", default=None,
                        help="Repeatable. Format LABEL:TIF:CONFIG")
    parser.add_argument("--shakefile", default=None)
    parser.add_argument("--rupture", default=None)
    parser.add_argument("--contours", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--infojson", default=None,
                        help="Path to gfailbin info.json for alert levels")
    args = parser.parse_args()

    # Load alert info from gfailbin info.json if provided
    alert_info = {}
    if args.infojson and os.path.exists(args.infojson):
        with open(args.infojson) as f:
            info = json.load(f)
        for model in info.get('Landslides', []) + info.get('Liquefaction', []):
            key = model['id']
            alert_info[key] = {
                'alert': model.get('alert', ''),
                'hazard_alert': model.get('hazard_alert', {}),
                'population_alert': model.get('population_alert', {}),
            }

    if args.model:
        model_specs = []
        for spec in args.model:
            parts = spec.split(":", 2)
            if len(parts) != 3:
                parser.error(f"--model must be LABEL:TIF:CONFIG, got: {spec}")
            model_specs.append(tuple(parts))
    else:
        if not args.tif:
            parser.error("must pass either --tif or one or more --model")
        model_specs = [(args.title, args.tif, args.config or "")]

    epi_lat, epi_lon, magnitude, description = (None, None, None, "")
    if args.shakefile:
        epi_lat, epi_lon, magnitude, description = get_epicenter(args.shakefile)

    rendered = []
    for label, tif_path, cfg_path in model_specs:
        tif_path = os.path.expanduser(tif_path)
        cfg_path = os.path.expanduser(cfg_path) if cfg_path else ""

        if not os.path.exists(tif_path):
            print(f"\nERROR: {tif_path} not found.")
            print("Run gfailbin for this model first, then re-run this script.")
            sys.exit(1)

        bins, cfg_threshold, cfg_cmap = (None, None, None)
        if cfg_path and os.path.exists(cfg_path):
            bins, cfg_threshold, cfg_cmap = read_config(cfg_path)
        threshold = args.threshold or cfg_threshold or 0.002
        cmap_name = cfg_cmap or "CMRmap_r"
        print(f"Reading {tif_path}...")
        img_b64, bounds, vmin, vmax, norm, cmap, rgba_arr = tif_to_png_overlay(
            tif_path, cmap_name, bins, threshold)
        max_p, pct_above = panel_stats(tif_path, threshold)
        rendered.append({
            "label": label, "img_b64": img_b64, "rgba": rgba_arr, "bounds": bounds,
            "norm": norm, "cmap": cmap, "bins": bins,
            "max_p": max_p, "pct_above": pct_above, "threshold": threshold,
        })

    west, south, east, north = rendered[0]["bounds"]
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2

    # use OpenStreetMap as default — Stamen tiles moved to Stadia in 2023
    # and old URLs are unreliable; add terrain via a named TileLayer instead
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,     # scale bar
    )
    folium.LatLngPopup().add_to(m)   # click anywhere to see coordinates

    folium.TileLayer("CartoDB positron", name="Light basemap").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Topo").add_to(m)
    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.jpg",
        attr="Stadia / Stamen", name="Terrain").add_to(m)

    for r in rendered:
        w, s, e, n = r["bounds"]
        folium.raster_layers.ImageOverlay(
            image=r["rgba"],
            bounds=[[s, w], [n, e]],
            opacity=1.0, name=r["label"], mercator_project=True, interactive=False, zindex=1,
        ).add_to(m)

    if args.contours and os.path.exists(args.contours):
        folium.GeoJson(
            args.contours, name="Shaking contours",
            style_function=lambda x: {
                "color": x["properties"].get("color", "black"),
                "weight": 2,
                "fillOpacity": 0
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["value", "units"],
                aliases=["MMI:", "Units:"],
                localize=True
            )
        ).add_to(m)

    if args.rupture and os.path.exists(args.rupture):
        folium.GeoJson(
            args.rupture, name="Fault rupture",
            style_function=lambda x: {"color": "red", "weight": 2, "fillOpacity": 0}
        ).add_to(m)

    if epi_lat is not None:
        folium.Marker(
            location=[epi_lat, epi_lon],
            tooltip=f"Epicenter M{magnitude:.1f} — {description}",
            icon=folium.Icon(icon="star", color="red", prefix="fa")
        ).add_to(m)

    folium.LayerControl(position="bottomright", collapsed=False).add_to(m)

    # colorbar + stats box — note: reflects first model only when multi-model
    primary = rendered[0]
    cb_b64 = make_colorbar(primary["cmap"], primary["norm"], primary["bins"], "Probability")
    # build stats line, add alert info if available
    _ak = next((k for k in alert_info if k in primary["label"].lower()), None)
    _ai = alert_info.get(_ak, {})
    _ha = _ai.get("hazard_alert", {})
    _pa = _ai.get("population_alert", {})
    _alert_str = ""
    if _ai:
        _col = {"green":"#2ecc40","yellow":"#ffdc00",
                "orange":"#ff851b","red":"#ff4136"}.get(_ai.get("alert",""),"#aaa")
        _alert_str = (f" &nbsp;|&nbsp; <span style='color:{_col};font-weight:bold'>{_ai.get('alert','').upper()}</span>"
                      f" &nbsp;|&nbsp; Pop: {_pa.get('value',0):,.0f}")
    stats_html = (f"Max P: {primary['max_p']:.3f} &nbsp;|&nbsp; "
                  f"Area &gt;threshold: {primary['pct_above']:.1f}%{_alert_str}")
    colorbar_label = (primary["label"] if len(rendered) == 1
                      else f"{primary['label']} (colorbar reflects this layer only)")
    colorbar_html = f"""
    <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
                background:white; padding:8px 12px; border-radius:6px;
                box-shadow:2px 2px 6px rgba(0,0,0,0.3); min-width:280px;">
        <div style="font-size:12px; font-weight:bold; margin-bottom:4px;">
            {colorbar_label}</div>
        <img src="data:image/png;base64,{cb_b64}" style="width:100%;">
        <div style="font-size:10px; margin-top:4px; color:#444;">
            {stats_html}</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(colorbar_html))

    if len(rendered) == 2:
        # Side-by-side layout: two separate maps in one HTML page
        maps = []
        for r in rendered:
            mi = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=7,
                tiles="OpenStreetMap",
                control_scale=True,
            )
            folium.LatLngPopup().add_to(mi)
            folium.TileLayer("CartoDB positron", name="Light basemap").add_to(mi)
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
                attr="Esri", name="Topo").add_to(mi)
            w, s, e, n = r["bounds"]
            folium.raster_layers.ImageOverlay(
                image=r["rgba"],
                bounds=[[s, w], [n, e]],
                opacity=1.0, name=r["label"], mercator_project=True, interactive=False, zindex=1,
            ).add_to(mi)
            if args.contours and os.path.exists(args.contours):
                folium.GeoJson(
                    args.contours, name="Shaking contours",
                    style_function=lambda x: {
                        "color": x["properties"].get("color", "black"),
                        "weight": 2,
                        "fillOpacity": 0
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["value", "units"],
                        aliases=["MMI:", "Units:"],
                        localize=True
                    )
                ).add_to(mi)
            if epi_lat is not None:
                folium.Marker(
                    location=[epi_lat, epi_lon],
                    tooltip=f"Epicenter M{magnitude:.1f} — {description}",
                    icon=folium.Icon(icon="star", color="red", prefix="fa")
                ).add_to(mi)
            folium.LayerControl(position="bottomright", collapsed=False).add_to(mi)
            # colorbar embedded in map
            cb_b64 = make_colorbar(r["cmap"], r["norm"], r["bins"], "Probability")
            cb_html = f"""
            <div style="position:fixed; bottom:10px; left:10px; z-index:1000;
                        background:rgba(255,255,255,0.92); padding:6px 10px;
                        border-radius:4px; box-shadow:1px 1px 4px rgba(0,0,0,0.2);
                        min-width:200px;">
                <img src="data:image/png;base64,{cb_b64}" style="width:100%;">
            </div>
            """
            mi.get_root().html.add_child(folium.Element(cb_html))
            maps.append(mi)

        # Build stats table rows
        ALERT_COL = {"green":"#27ae60","yellow":"#f39c12",
                     "orange":"#e67e22","red":"#c0392b"}
        table_rows = ""
        hazard_types = ["Landslide", "Liquefaction"]
        for i, r in enumerate(rendered):
            _ak = next((k for k in alert_info
                        if k.replace('_','') in r['label'].lower().replace('_','')
                        or r['label'].lower().replace('_','') in k.replace('_','')), None)
            _ai = alert_info.get(_ak, {})
            _ha = _ai.get("hazard_alert", {})
            _pa = _ai.get("population_alert", {})
            hcol = ALERT_COL.get(_ha.get("color",""), "#888")
            pcol = ALERT_COL.get(_pa.get("color",""), "#888")
            ha_str = (f"<span style='color:{hcol};font-weight:bold'>"
                      f"{_ha.get('color','—').upper()}</span> "
                      f"({_ha.get('value',0):.0f} {_ha.get('units','')})") if _ha else "—"
            pa_str = (f"<span style='color:{pcol};font-weight:bold'>"
                      f"{_pa.get('color','—').upper()}</span> "
                      f"({_pa.get('value',0):,.0f} {_pa.get('units','')})") if _pa else "—"
            oa = _ai.get('alert','')
            oa_col = ALERT_COL.get(oa, '#888')
            oa_str = f"<span style='color:{oa_col};font-weight:bold'>{oa.upper()}</span>" if oa else '—'
            table_rows += f"""
            <tr>
                <td>{r['label']}</td>
                <td>{hazard_types[i] if i < len(hazard_types) else ''}</td>
                <td>{oa_str}</td>
                <td>{ha_str}</td>
                <td>{pa_str}</td>
            </tr>"""

        # Render each map and combine
        html1 = maps[0].get_root().render()
        html2 = maps[1].get_root().render()
        event_title = description if description else "Ground Failure"
        combined = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: sans-serif; display: flex; flex-direction: column;
          height: 100vh; background: #f5f5f5; }}
  .header {{ background: #1B2A4A; color: white; padding: 8px 16px;
             font-size: 15px; font-weight: bold; flex-shrink: 0; }}
  .maps {{ display: flex; flex: 1; min-height: 0; }}
  .panel {{ flex: 1; display: flex; flex-direction: column;
            border-right: 2px solid #1B2A4A; }}
  .panel:last-child {{ border-right: none; }}
  .panel-title {{ text-align: center; padding: 5px; font-size: 13px;
                  font-weight: bold; background: #2c3e6b; color: white; }}
  .panel iframe {{ flex: 1; border: none; }}
  .stats {{ flex-shrink: 0; background: white; border-top: 2px solid #1B2A4A;
            padding: 8px 16px; }}
  .stats table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .stats th {{ background: #1B2A4A; color: white; padding: 5px 10px;
               text-align: left; }}
  .stats td {{ padding: 5px 10px; border-bottom: 1px solid #ddd; }}
  .stats tr:last-child td {{ border-bottom: none; }}
</style>
</head>
<body>
<div class="header">Ground Failure — {event_title}</div>
<div class="maps">
  <div class="panel">
    <div class="panel-title">{rendered[0]['label']}</div>
    <iframe srcdoc="{html1.replace(chr(34), '&quot;')}"></iframe>
  </div>
  <div class="panel">
    <div class="panel-title">{rendered[1]['label']}</div>
    <iframe srcdoc="{html2.replace(chr(34), '&quot;')}"></iframe>
  </div>
</div>
<div class="stats">
  <table>
    <tr><th>Model</th><th>Hazard type</th><th>Overall alert</th><th>Hazard alert</th><th>Population alert</th></tr>
    {table_rows}
  </table>
</div>
</body>
</html>"""
        with open(args.outfile, "w") as f:
            f.write(combined)
    else:
        m.save(args.outfile)

    print(f"Saved: {args.outfile}")
    for r in rendered:
        print(f"[{r['label']}] max P: {r['max_p']:.4f}, "
              f"area>{r['threshold']}: {r['pct_above']:.1f}%")


if __name__ == "__main__":
    main()