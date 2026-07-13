"""
plot_gf_interactive.py — interactive HTML map of a groundfailure model output.

Usage:
    python plot_gf_interactive.py --tif <model.tif> --outfile <output.html>
                                  [--title "My map title"]
                                  [--cmap viridis] [--vmin 0] [--vmax 1]
                                  [--threshold 0.02]

Arguments:
    --tif        Path to a groundfailure _model.tif (from gfailbin --gis)
    --outfile    Output HTML file (default: groundfailure_map.html)
    --title      Map title shown in legend (default: Ground Failure Model)
    --cmap       Matplotlib colormap name (default: CMRmap_r)
    --vmin       Colorbar minimum (default: auto from data)
    --vmax       Colorbar maximum (default: auto from data)
    --threshold  Values below this are masked/transparent (default: 0.002)

Example:
    python plot_gf_interactive.py \\
        --tif ~/gf_turkey/us6000jlqa/us6000jlqa_nowicki_2014_global_slim_model.tif \\
        --outfile ~/turkey_gf_map.html \\
        --title "Nowicki 2014 Landslide — Turkey M7.5"
"""

import argparse
import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import rasterio
import rasterio.warp
import folium


def tif_to_png_overlay(tif_path, cmap, vmin, vmax, threshold):
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
        bounds_src = src.bounds
        crs = src.crs

        # reproject bounds to WGS84 for folium
        if crs.to_epsg() != 4326:
            bounds_wgs84 = rasterio.warp.transform_bounds(
                crs, "EPSG:4326",
                bounds_src.left, bounds_src.bottom,
                bounds_src.right, bounds_src.top
            )
        else:
            bounds_wgs84 = (
                bounds_src.left, bounds_src.bottom,
                bounds_src.right, bounds_src.top
            )

    if nodata is not None:
        data[data == nodata] = np.nan
    data[data < threshold] = np.nan

    if vmin is None:
        vmin = float(np.nanpercentile(data, 2))
    if vmax is None:
        vmax = float(np.nanpercentile(data, 98))

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cm = plt.get_cmap(cmap)

    rgba = cm(norm(data))
    rgba[..., 3] = np.where(np.isnan(data), 0, 0.7)

    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return img_b64, bounds_wgs84, vmin, vmax, norm, cm


def make_colorbar(cmap, vmin, vmax, title):
    fig, ax = plt.subplots(figsize=(4, 0.4))
    fig.subplots_adjust(bottom=0.5)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cb = plt.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=plt.get_cmap(cmap)),
        cax=ax, orientation="horizontal"
    )
    cb.set_label(title, fontsize=9)
    ax.tick_params(labelsize=8)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True, dpi=120)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return b64


def main():
    parser = argparse.ArgumentParser(
        description="Interactive HTML map of a groundfailure model output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--tif", required=True, help="Path to _model.tif from gfailbin")
    parser.add_argument("--outfile", default="groundfailure_map.html")
    parser.add_argument("--title", default="Ground Failure Model")
    parser.add_argument("--cmap", default="CMRmap_r")
    parser.add_argument("--vmin", type=float, default=None)
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--threshold", type=float, default=0.002)
    args = parser.parse_args()

    print(f"Reading {args.tif}...")
    img_b64, bounds, vmin, vmax, norm, cm = tif_to_png_overlay(
        args.tif, args.cmap, args.vmin, args.vmax, args.threshold
    )

    west, south, east, north = bounds
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles="OpenStreetMap"
    )

    folium.TileLayer("CartoDB positron", name="Light basemap").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
    ).add_to(m)

    img_url = f"data:image/png;base64,{img_b64}"
    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=[[south, west], [north, east]],
        opacity=1.0,
        name=args.title,
        interactive=False,
        zindex=1,
    ).add_to(m)

    cb_b64 = make_colorbar(args.cmap, vmin, vmax, "Probability")
    colorbar_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 8px; border-radius: 6px;
                box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
        <div style="font-size:12px; font-weight:bold; margin-bottom:4px;">{args.title}</div>
        <img src="data:image/png;base64,{cb_b64}" style="width:260px;">
    </div>
    """
    m.get_root().html.add_child(folium.Element(colorbar_html))

    folium.LayerControl().add_to(m)

    m.save(args.outfile)
    print(f"Saved: {args.outfile}")
    print(f"Open with: code {args.outfile}")
    print(f"Value range shown: {vmin:.4f} – {vmax:.4f}")


if __name__ == "__main__":
    main()
