#!/usr/bin/env python3
"""
plot_gf_interactive.py — interactive HTML map of a groundfailure model output.

Usage:
    python plot_gf_interactive.py --tif <model.tif> --outfile <output.html>
                                  [--title "My map title"]
                                  [--config  path/to/model.ini]
                                  [--shakefile path/to/grid.xml]
                                  [--rupture  path/to/rupture.json]
                                  [--contours path/to/cont_mmi.json]
                                  [--threshold 0.002]

Arguments:
    --tif        Path to a groundfailure _model.tif (from gfailbin --gis)
    --outfile    Output HTML file (default: groundfailure_map.html)
    --title      Map title shown in legend (default: Ground Failure Model)
    --config     Path to the gfailbin .ini config for this model -- reads bins
                 and colormap from [[display_options]] so the map matches the
                 static plot and operational kmz output exactly
    --shakefile  ShakeMap grid.xml -- adds epicenter marker and event metadata
    --rupture    rupture.json from ShakeMap products -- adds finite fault overlay
    --contours   A ShakeMap contour GeoJSON (e.g. cont_mmi.json) -- adds
                 shaking contours as a toggleable layer
    --threshold  Values below this are masked/transparent (default: from config,
                 or 0.002 if no config given)

Example:
    python plot_gf_interactive.py \\
        --tif ~/gf_turkey/us6000jlqa/us6000jlqa_nowicki_2014_global_slim_model.tif \\
        --config ~/groundfailure/defaultconfigfiles/models/nowicki_2014_global_slim.ini \\
        --shakefile ~/shakemap_profiles/default/data/us6000jlqa/current/products/grid.xml \\
        --rupture ~/shakemap_profiles/default/data/us6000jlqa/current/products/rupture.json \\
        --contours ~/shakemap_profiles/default/data/us6000jlqa/current/products/cont_mmi.json \\
        --outfile ~/turkey_gf_map.html \\
        --title "Nowicki 2014 Landslide — Turkey M7.5"
"""

import argparse
import io
import base64
import os
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
    """Read bins, colormap, and threshold from a gfailbin .ini file."""
    try:
        from configobj import ConfigObj
        cfg = ConfigObj(config_path)
        model_name = list(cfg.keys())[0]
        disp = cfg[model_name].get("display_options", {})
        lims_str = disp.get("lims", {}).get("model", None)
        thresh_str = disp.get("maskthresholds", {}).get("model", None)
        cmap_str = disp.get("colors", {}).get("model", None)
        bins = ([float(x.strip()) for x in lims_str.split(",")]
                if lims_str and lims_str != "None" else None)
        threshold = (float(thresh_str)
                     if thresh_str and thresh_str != "None" else None)
        cmap = cmap_str.replace("cm.", "") if cmap_str and cmap_str != "None" else None
        return bins, threshold, cmap
    except Exception:
        return None, None, None


def get_epicenter(shakefile):
    """Parse epicenter and magnitude from a ShakeMap grid.xml."""
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
    rgba[..., 3] = np.where(np.isnan(data), 0, 0.75)

    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_b64, bounds_wgs84, vmin, vmax, norm, cmap


def make_colorbar(cmap, norm, bins, title):
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
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True, dpi=120)
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
        description="Interactive HTML map of a groundfailure model output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument("--tif", required=True)
    parser.add_argument("--outfile", default="groundfailure_map.html")
    parser.add_argument("--title", default="Ground Failure Model")
    parser.add_argument("--config", default=None)
    parser.add_argument("--shakefile", default=None)
    parser.add_argument("--rupture", default=None)
    parser.add_argument("--contours", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    # read bins, cmap, threshold from config if provided
    bins, cfg_threshold, cfg_cmap = (None, None, None)
    if args.config:
        bins, cfg_threshold, cfg_cmap = read_config(args.config)

    threshold = args.threshold or cfg_threshold or 0.002
    cmap_name = cfg_cmap or "CMRmap_r"

    # epicenter from shakefile
    epi_lat, epi_lon, magnitude, description = (None, None, None, "")
    if args.shakefile:
        epi_lat, epi_lon, magnitude, description = get_epicenter(args.shakefile)

    # stats
    max_p, pct_above = panel_stats(args.tif, threshold)

    print(f"Reading {args.tif}...")
    img_b64, bounds, vmin, vmax, norm, cmap = tif_to_png_overlay(
        args.tif, cmap_name, bins, threshold)

    west, south, east, north = bounds
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7,
                   tiles="OpenStreetMap")
    folium.TileLayer("CartoDB positron", name="Light basemap").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Satellite").add_to(m)

    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{img_b64}",
        bounds=[[south, west], [north, east]],
        opacity=1.0, name=args.title, interactive=False, zindex=1,
    ).add_to(m)

    # shaking contours
    if args.contours and os.path.exists(args.contours):
        folium.GeoJson(
            args.contours, name="Shaking contours",
            style_function=lambda x: {"color": "black", "weight": 1,
                                       "dashArray": "5,5", "fillOpacity": 0}
        ).add_to(m)

    # finite fault
    if args.rupture and os.path.exists(args.rupture):
        folium.GeoJson(
            args.rupture, name="Fault rupture",
            style_function=lambda x: {"color": "red", "weight": 2, "fillOpacity": 0}
        ).add_to(m)

    # epicenter marker
    if epi_lat is not None:
        folium.Marker(
            location=[epi_lat, epi_lon],
            tooltip=f"Epicenter M{magnitude:.1f} — {description}",
            icon=folium.Icon(icon="star", color="red", prefix="fa")
        ).add_to(m)

    folium.LayerControl().add_to(m)

    cb_b64 = make_colorbar(cmap, norm, bins, "Probability")
    stats_html = (f"Max P: {max_p:.3f} &nbsp;|&nbsp; "
                  f"Area &gt;threshold: {pct_above:.1f}%")
    colorbar_html = f"""
    <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
                background:white; padding:8px 12px; border-radius:6px;
                box-shadow:2px 2px 6px rgba(0,0,0,0.3); min-width:280px;">
        <div style="font-size:12px; font-weight:bold; margin-bottom:4px;">
            {args.title}</div>
        <img src="data:image/png;base64,{cb_b64}" style="width:100%;">
        <div style="font-size:10px; margin-top:4px; color:#444;">
            {stats_html}</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(colorbar_html))

    m.save(args.outfile)
    print(f"Saved: {args.outfile}")
    print(f"Max probability: {max_p:.4f}")
    print(f"Area above threshold ({threshold}): {pct_above:.1f}%")
    

if __name__ == "__main__":
    main()
