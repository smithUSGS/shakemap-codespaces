#!/usr/bin/env python3
"""
plot_gf_interactive.py

Creates two side-by-side interactive HTML maps (landslides + liquefaction)
from groundfailure model outputs, following the USGS operational style.

Usage:
    python plot_gf_interactive.py \
        --ls-model "LABEL:TIF:CONFIG" [--ls-model ...] \
        --lq-model "LABEL:TIF:CONFIG" [--lq-model ...] \
        [--shakefile path/to/grid.xml] \
        [--rupture   path/to/rupture.json] \
        [--contours  path/to/cont_mmi.json] \
        --outfile    output.html

Produces a single self-contained HTML with landslide map (left) and
liquefaction map (right). Each map has its own branca colorbars, a
layer-switcher for multiple models, shaking contours, fault trace,
epicenter marker, scale bar, and coordinate popup.

Example:
    python plot_gf_interactive.py \
        --ls-model "Nowicki Jessee (2018):~/gf/jessee_model.tif:~/cfg/jessee_2018_slim.ini" \
        --lq-model "Zhu and others (2017):~/gf/zhu_model.tif:~/cfg/zhu_2017_general_slim.ini" \
        --shakefile ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \
        --contours  ~/shakemap_profiles/default/data/us6000jlqa/current/products/cont_mmi.json \
        --outfile   ~/turkey_gf.html
"""

import argparse
import base64
import io
import os
import tempfile
import xml.etree.ElementTree as ET

import branca.colormap as cmb
import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import rasterio.warp


def read_config(config_path):
    try:
        from configobj import ConfigObj
        cfg = ConfigObj(config_path)
        mn = list(cfg.keys())[0]
        disp = cfg[mn].get("display_options", {})
        ls = disp.get("lims", {}).get("model", None)
        ts = disp.get("maskthresholds", {}).get("model", None)
        cs = disp.get("colors", {}).get("model", None)
        bins = ([float(x.strip()) for x in ls.split(",")]
                if ls and ls != "None" else None)
        threshold = (float(ts) if ts and ts != "None" else None)
        cmap = cs.replace("cm.", "") if cs and cs != "None" else None
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


def get_title(shakefile):
    try:
        ns = {"sm": "http://earthquake.usgs.gov/eqcenter/shakemap"}
        root = ET.parse(shakefile).getroot()
        ev = root.find("sm:event", ns).attrib
        ts = ev.get("event_timestamp", "")[:10]
        return "M%.1f %s \u2014 %s" % (
            float(ev.get("magnitude", 0)), ts,
            ev.get("event_description", ""))
    except Exception:
        return "Ground Failure"


def tif_to_rgba(tif_path, cmap_name, bins, threshold):
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
        b = src.bounds
        crs = src.crs
        if crs.to_epsg() != 4326:
            bounds = rasterio.warp.transform_bounds(
                crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
        else:
            bounds = (b.left, b.bottom, b.right, b.top)
    if nodata is not None:
        data[data == nodata] = np.nan
    data[data < threshold] = np.nan
    cmap = plt.get_cmap(cmap_name)
    if bins is not None:
        norm = mcolors.BoundaryNorm(bins, cmap.N)
    else:
        vmin = float(np.nanpercentile(data, 2))
        vmax = float(np.nanpercentile(data, 98))
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    rgba = cmap(norm(data))
    rgba[..., 3] = np.where(np.isnan(data), 0, 0.7)
    rgba_uint8 = (rgba * 255).astype(np.uint8)
    return rgba_uint8, bounds, norm, cmap


def rgba_to_b64(rgba_uint8):
    buf = io.BytesIO()
    plt.imsave(buf, rgba_uint8.astype(np.float32) / 255.0, format="png")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def panel_stats(tif_path, threshold):
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nd = src.nodata
    if nd is not None:
        data[data == nd] = np.nan
    valid = data[~np.isnan(data)]
    if len(valid) == 0:
        return 0.0, 0.0
    above = float(np.sum(data > threshold))
    return float(np.nanmax(data)), 100.0 * above / len(valid)


def make_branca_colormap(cmap_name, bins, threshold, label):
    cmap_mpl = plt.get_cmap(cmap_name)
    if bins is not None:
        norm = mcolors.BoundaryNorm(bins, cmap_mpl.N)
        mids = [(bins[i] + bins[i + 1]) / 2.0 for i in range(len(bins) - 1)]
        colors_hex = [mcolors.to_hex(cmap_mpl(norm(m))) for m in mids]
        return cmb.StepColormap(
            colors_hex, vmin=bins[0], vmax=bins[-1],
            index=bins, caption=label)
    else:
        colors_hex = [mcolors.to_hex(cmap_mpl(x)) for x in np.linspace(0, 1, 10)]
        return cmb.LinearColormap(
            colors_hex, vmin=threshold or 0.0, vmax=1.0, caption=label)


def removeVis(filename, removelater, mapname):
    replacetext = ".addTo(%s)" % mapname
    with open(filename, "r") as f:
        lines = f.readlines()
    for remove in removelater:
        newlines = []
        r1 = False
        for line in lines:
            newline = line
            if "var %s" % remove in line:
                r1 = True
            if r1 and replacetext in line:
                newline = line.replace(replacetext, "")
                r1 = False
            newlines.append(newline)
        lines = newlines
    with open(filename, "w") as f:
        f.writelines(lines)


def build_map(models, epicenter, contours_file, rupture_file):
    if not models:
        return None, []

    w, s, e, n = models[0]["bounds"]
    m = folium.Map(
        location=[(s + n) / 2.0, (w + e) / 2.0],
        zoom_start=7,
        tiles="CartoDB positron",
        control_scale=True)
    folium.LatLngPopup().add_to(m)
    m.get_root().html.add_child(folium.Element(
    "<style>"
    "div.legend{background:rgba(255,255,255,0.92)!important;"
    "padding:6px 10px!important;border-radius:4px!important;"
    "color:#000!important;}"
    "</style>"))

    map_name = m.get_name()
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Satellite").add_to(m)

    # Model image overlays
    removelater = []
    for i, r in enumerate(models):
        bw = r["bounds"]
        img_b64 = rgba_to_b64(r["rgba"])
        fg = folium.FeatureGroup(name=r["label"], show=True, overlay=True)
        folium.raster_layers.ImageOverlay(
            image="data:image/png;base64," + img_b64,
            bounds=[[bw[1], bw[0]], [bw[3], bw[2]]],
            opacity=1.0, interactive=False, zindex=i + 1,
        ).add_to(fg)
        fg.add_to(m)
        if i > 0:
            removelater.append(fg.get_name())
        cb = make_branca_colormap(
            r["cmap_name"], r["bins"], r["threshold"],
            "%s (max P=%.3f)" % (r["label"], r["max_p"]))
        cb.add_to(m)

    if contours_file and os.path.exists(contours_file):
        contours_layer = folium.GeoJson(
            contours_file,
            name="Shaking contours",
            style_function=lambda x: {
                "color": "#333", "weight": 2.0,
                "dashArray": "5,5", "fillOpacity": 0, "opacity": 1.0},
        )
        contours_layer.add_to(m)
        contours_var = contours_layer.get_name()

        m.get_root().html.add_child(folium.Element(
            "<script>document.addEventListener('DOMContentLoaded',function(){setTimeout(function(){"
            "try{"
            "var lm=window['%s'];"
            "var pane=lm.getPane('contoursPane');"
            "if(!pane){pane=lm.createPane('contoursPane');pane.style.zIndex=650;}"
            "var cl=window['%s'];"
            "if(cl){"
            "cl.eachLayer(function(l){"
            "if(l._path){pane.appendChild(l._path);}"
            "if(l._layers){"
            "Object.values(l._layers).forEach(function(sub){"
            "if(sub._path){pane.appendChild(sub._path);}"
            "});}"
            "});}"
            "}catch(e){console.warn('contours fix:',e);}"
            "}, 500);</script>" % (map_name, contours_var)
        ))

    if rupture_file and os.path.exists(rupture_file):
        folium.GeoJson(
            rupture_file, name="Fault rupture",
            style_function=lambda x: {
                "color": "red", "weight": 2, "fillOpacity": 0},
            pane="contoursPane",
        ).add_to(m)

    epi_lat, epi_lon, magnitude, description = epicenter
    if epi_lat is not None:
        folium.Marker(
            location=[epi_lat, epi_lon],
            icon=folium.DivIcon(
                html='<div style="width:14px;height:14px;border-radius:50%;'
                    'background:white;border:2.5px solid black;"></div>',
                icon_size=(14, 14),
                icon_anchor=(7, 7),
            ),
            tooltip="Epicenter M%.1f \u2014 %s" % (magnitude, description),
        ).add_to(m)

    folium.LayerControl(collapsed=False, position="bottomright").add_to(m)
    return m, removelater


def main():
    p = argparse.ArgumentParser(
        description="Two-panel interactive ground failure map (LS + LQ).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--ls-model", dest="ls_models", action="append",
                   default=[], metavar="LABEL:TIF:CONFIG")
    p.add_argument("--lq-model", dest="lq_models", action="append",
                   default=[], metavar="LABEL:TIF:CONFIG")
    p.add_argument("--shakefile", default=None)
    p.add_argument("--rupture", default=None)
    p.add_argument("--contours", default=None)
    p.add_argument("--outfile", default="groundfailure_map.html")
    args = p.parse_args()

    if not args.ls_models and not args.lq_models:
        p.error("provide at least one --ls-model or --lq-model")

    def parse_specs(specs):
        out = []
        for spec in specs:
            parts = spec.split(":", 2)
            if len(parts) != 3:
                p.error("must be LABEL:TIF:CONFIG, got: %s" % spec)
            out.append(tuple(parts))
        return out

    ls_specs = parse_specs(args.ls_models)
    lq_specs = parse_specs(args.lq_models)

    epicenter = (None, None, None, "")
    title = "Ground Failure"
    if args.shakefile:
        epicenter = get_epicenter(args.shakefile)
        title = get_title(args.shakefile)

    def load_models(specs, haz):
        models = []
        for label, tif_path, cfg_path in specs:
            tif_path = os.path.expanduser(tif_path)
            cfg_path = os.path.expanduser(cfg_path) if cfg_path else ""
            bins, cfg_thresh, cfg_cmap = (None, None, None)
            if cfg_path and os.path.exists(cfg_path):
                bins, cfg_thresh, cfg_cmap = read_config(cfg_path)
            threshold = cfg_thresh or 0.002
            cmap_name = cfg_cmap or "CMRmap_r"
            print("Loading [%s] %s" % (haz, label))
            rgba, bounds, norm, cmap = tif_to_rgba(
                tif_path, cmap_name, bins, threshold)
            max_p, pct = panel_stats(tif_path, threshold)
            models.append(dict(
                label=label, rgba=rgba, bounds=bounds,
                norm=norm, cmap=cmap, cmap_name=cmap_name,
                bins=bins, threshold=threshold,
                max_p=max_p, pct_above=pct))
        return models

    ls_models = load_models(ls_specs, "LS")
    lq_models = load_models(lq_specs, "LQ")

    tmpdir = tempfile.mkdtemp()

    def render_map(models, tmp_name):
        if not models:
            return ""
        folium_map, removelater = build_map(
            models, epicenter, args.contours, args.rupture)
        fpath = os.path.join(tmpdir, tmp_name)
        folium_map.save(fpath)
        if removelater:
            removeVis(fpath, removelater, folium_map.get_name())
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read()

    ls_html = render_map(ls_models, "ls.html")
    lq_html = render_map(lq_models, "lq.html")

    def to_uri(html_str):
        b64 = base64.b64encode(html_str.encode("utf-8")).decode("ascii")
        return "data:text/html;charset=utf-8;base64," + b64

    panels = []
    if ls_html:
        panels.append(("Landslides", ls_html))
    if lq_html:
        panels.append(("Liquefaction", lq_html))

    panel_divs = ""
    for ptitle, html in panels:
        panel_divs += (
            '<div class="panel">'
            '<div class="panel-title">%s</div>'
            '<iframe src="%s" class="map-frame"></iframe>'
            '</div>' % (ptitle, to_uri(html)))

    stats_rows = ""
    for r in ls_models:
        stats_rows += ("<tr><td>%s</td><td>Landslide</td>"
                       "<td>%.3f</td><td>%.1f%%</td></tr>"
                       % (r["label"], r["max_p"], r["pct_above"]))
    for r in lq_models:
        stats_rows += ("<tr><td>%s</td><td>Liquefaction</td>"
                       "<td>%.3f</td><td>%.1f%%</td></tr>"
                       % (r["label"], r["max_p"], r["pct_above"]))

    combined = (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'><title>%s</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee}"
        ".header{padding:10px 20px;background:#16213e;"
        "font-size:16px;font-weight:bold;border-bottom:2px solid #0f3460}"
        ".maps{display:flex;height:calc(100vh - 130px)}"
        ".panel{flex:1;display:flex;flex-direction:column;"
        "border-right:2px solid #0f3460}"
        ".panel:last-child{border-right:none}"
        ".panel-title{text-align:center;padding:5px;background:#0f3460;"
        "font-size:13px;font-weight:bold;letter-spacing:0.5px}"
        ".map-frame{flex:1;border:none;width:100%%}"
        ".stats{padding:8px 20px;background:#16213e;"
        "border-top:2px solid #0f3460;font-size:12px}"
        ".stats table{border-collapse:collapse;width:100%%}"
        ".stats th,.stats td{padding:3px 10px;border:1px solid #0f3460;text-align:left}"
        ".stats th{background:#0f3460}"
        "</style></head><body>"
        "<div class='header'>Ground Failure \u2014 %s</div>"
        "<div class='maps'>%s</div>"
        "<div class='stats'><table>"
        "<tr><th>Model</th><th>Hazard type</th>"
        "<th>Max probability</th><th>Area above threshold</th></tr>"
        "%s</table></div>"
        "</body></html>"
    ) % (title, title, panel_divs, stats_rows)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(combined)

    print("Saved: %s" % args.outfile)
    for r in ls_models:
        print("[LS] %s: max P=%.4f, area>%.3f: %.1f%%"
              % (r["label"], r["max_p"], r["threshold"], r["pct_above"]))
    for r in lq_models:
        print("[LQ] %s: max P=%.4f, area>%.3f: %.1f%%"
              % (r["label"], r["max_p"], r["threshold"], r["pct_above"]))


if __name__ == "__main__":
    main()
