#!/usr/bin/env python3
"""
groundfailure_maps.py — static 3-panel ground failure map.

Usage:
    python groundfailure_maps.py \\
        --shakefile northridge.xml \\
        --datadir /path/to/model_inputs \\
        --outfile northridge_groundfailure.png

Optional overlays (all paths to files from the ShakeMap products folder):
    --rupture   rupture.json     finite fault trace (red line)
    --contours  cont_mmi.json    MMI shaking contours (dashed black)
    --hillshade hillshade.tif    hillshade raster drawn under model overlay

Model-parameter overrides (all have defaults from the .ini files):
    --thick, --uwt, --codiv, --nodata-cohesion, --nodata-friction,
    --fsthresh, --acthresh, --dnthresh, --slopemin, --minpga
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
from scipy.ndimage import binary_fill_holes, binary_closing


def parse_shakemap_grid(shakefile):
    ns = {"sm": "http://earthquake.usgs.gov/eqcenter/shakemap"}
    tree = ET.parse(shakefile)
    root = tree.getroot()
    ev = root.find("sm:event", ns).attrib
    gs = root.find("sm:grid_specification", ns).attrib
    nlon, nlat = int(gs["nlon"]), int(gs["nlat"])
    fields = root.findall("sm:grid_field", ns)
    field_names = [f.attrib["name"] for f in fields]
    col_index = {name: i for i, name in enumerate(field_names)}
    gd_text = root.find("sm:grid_data", ns).text
    data = np.fromstring(gd_text, sep=" ", dtype=np.float64)
    data = data.reshape(nlon * nlat, len(field_names))

    def get2d(name):
        return data[:, col_index[name]].reshape(nlat, nlon)

    lons = get2d("LON")[0, :]
    lats = get2d("LAT")[:, 0]
    return {
        "pga": get2d("PGA"), "pgv": get2d("PGV"), "mmi": get2d("MMI"),
        "lons": lons, "lats": lats,
        "magnitude": float(ev["magnitude"]),
        "lat": float(ev["lat"]), "lon": float(ev["lon"]),
        "description": ev["event_description"],
        "event_timestamp": ev["event_timestamp"],
        "shakemap_version": root.attrib.get("shakemap_version", "1"),
    }


def resample_to_grid(path, lons, lats, resampling=Resampling.bilinear):
    nlat, nlon = len(lats), len(lons)
    dx = lons[1] - lons[0]
    dy = lats[0] - lats[1]
    dst_transform = from_bounds(
        lons.min() - dx / 2, lats.min() - dy / 2,
        lons.max() + dx / 2, lats.max() + dy / 2,
        nlon, nlat,
    )
    with rasterio.open(path) as src:
        dst = np.full((nlat, nlon), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1), destination=dst,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=dst_transform, dst_crs="EPSG:4326",
            resampling=resampling, src_nodata=src.nodata, dst_nodata=np.nan,
        )
    return dst


def compute_godt2008(lons, lats, pga_pctg, slope_dir, cohesion_file, friction_file,
                      thick=2.4, uwt=15.7, codiv=10.0,
                      nodata_cohesion=1.0, nodata_friction=26.0,
                      fsthresh=1.01, acthresh=0.05, dnthresh=5.0, slopemin=0.01):
    quantiles = ["slope_min.bil", "slope10.bil", "slope30.bil", "slope50.bil",
                 "slope70.bil", "slope90.bil", "slope_max.bil"]
    slopestack = np.dstack([
        resample_to_grid(os.path.join(slope_dir, q), lons, lats, Resampling.bilinear) / 100.0
        for q in quantiles
    ])
    slopestack[slopestack == 0] = 1e-8

    cohesion = np.nan_to_num(resample_to_grid(cohesion_file, lons, lats, Resampling.nearest))
    cohesion = np.repeat(cohesion[:, :, np.newaxis], 7, axis=2) / codiv
    cohesion[cohesion == 0] = nodata_cohesion

    friction = np.nan_to_num(resample_to_grid(friction_file, lons, lats, Resampling.nearest)).astype(float)
    friction = np.repeat(friction[:, :, np.newaxis], 7, axis=2)
    friction[friction == 0] = nodata_friction

    with np.errstate(invalid="ignore", divide="ignore"):
        FS = (cohesion / (uwt * thick * np.sin(slopestack * np.pi / 180.0))
              + np.tan(friction * np.pi / 180.0) / np.tan(slopestack * np.pi / 180.0))
    FS[FS < fsthresh] = fsthresh
    Ac = (FS - 1) * np.sin(slopestack * np.pi / 180.0)
    Ac[Ac < acthresh] = acthresh

    PGA = np.repeat((pga_pctg / 100.0)[:, :, np.newaxis], 7, axis=2)
    C1, C2, C3 = 0.215, 2.341, -1.438
    with np.errstate(invalid="ignore", divide="ignore"):
        Dn = 10.0 ** (C1 + np.log10(((1 - Ac / PGA) ** C2) * (Ac / PGA) ** C3))
    Dn[np.isnan(Dn)] = 0.0

    PROB = Dn.copy()
    PROB[PROB < dnthresh] = 0.0
    PROB[PROB >= dnthresh] = 1.0
    PROB = np.sum(PROB, axis=2)

    lookup = {1: 0.01, 2: 0.10, 3: 0.30, 4: 0.50, 5: 0.70, 6: 0.90, 7: 0.99}
    PROB_final = np.zeros_like(PROB)
    for count, prob in lookup.items():
        PROB_final[PROB == count] = prob
    PROB_final[slopestack[:, :, 6] <= slopemin] = 0.0
    return PROB_final


def compute_nowicki2014(lons, lats, pgv, slope_max_file, friction_file, cti_file,
                         minpga=2.0, nodata_friction=26.0):
    COEFFS = {"b0": -3.6490, "b1": 0.0133, "b2": 0.0364,
              "b3": -0.0635, "b4": -0.0004, "b5": 0.0019}
    slope_max = resample_to_grid(slope_max_file, lons, lats, Resampling.bilinear) / 100.0
    friction = resample_to_grid(friction_file, lons, lats, Resampling.nearest)
    cti = resample_to_grid(cti_file, lons, lats, Resampling.bilinear)
    friction_filled = np.nan_to_num(friction, nan=nodata_friction)
    cti_filled = np.nan_to_num(cti, nan=0.0)
    pgv_clip = np.clip(pgv, 0.0, 170.0)
    X = (COEFFS["b0"] + COEFFS["b1"] * pgv_clip + COEFFS["b2"] * slope_max
         + COEFFS["b3"] * friction_filled + COEFFS["b4"] * (cti_filled * 100)
         + COEFFS["b5"] * pgv_clip * slope_max)
    P = 1.0 / (1.0 + np.exp(-X))
    P[pgv_clip < minpga] = np.nan
    return P


def compute_zhu2017(lons, lats, pgv, vs30_file, precip_file, wtd_file, dc_file, dr_file):
    vs30 = resample_to_grid(vs30_file, lons, lats, Resampling.bilinear)
    precip = resample_to_grid(precip_file, lons, lats, Resampling.bilinear)
    wtd = resample_to_grid(wtd_file, lons, lats, Resampling.bilinear)
    dc = resample_to_grid(dc_file, lons, lats, Resampling.bilinear)
    dr = resample_to_grid(dr_file, lons, lats, Resampling.bilinear)
    dw = np.minimum(dc, dr)
    with np.errstate(invalid="ignore", divide="ignore"):
        X = (8.801 + 0.334 * np.log(pgv) - 1.918 * np.log(vs30)
             + 0.0005408 * precip - 0.2054 * dw - 0.0333 * wtd)
        P = 1.0 / (1.0 + np.exp(-X))
    P[pgv < 3.0] = 0.0
    P[vs30 > 620.0] = 0.0
    P[np.isnan(vs30) | np.isnan(precip) | np.isnan(wtd) | np.isnan(dw)] = np.nan
    return P


def derive_land_mask(lons, lats, landmask_source_file):
    raw = resample_to_grid(landmask_source_file, lons, lats, Resampling.nearest)
    land = ~np.isnan(raw)
    land = binary_closing(binary_fill_holes(land), structure=np.ones((3, 3)))
    return land


def panel_stats(data, threshold):
    valid = data[~np.isnan(data)]
    if len(valid) == 0:
        return 0.0, 0.0
    above = float(np.sum(data > threshold))
    return float(np.nanmax(data)), 100.0 * above / len(valid)


def plot_three_panel(lons, lats, godt_prob, nowicki_prob, liq_prob,
                      land_mask, event_meta, outfile,
                      rupture_file=None, contours_file=None, hillshade_file=None):
    extent = [lons.min(), lons.max(), lats.min(), lats.max()]
    epi_lat, epi_lon = event_meta["lat"], event_meta["lon"]
    proj = ccrs.PlateCarree()
    LON, LAT = np.meshgrid(lons, lats)

    # bins from default config files
    godt_lims    = [0.05, 0.10, 0.20, 0.42, 0.65, 0.81, 1.0]
    nowicki_lims = [0.07, 0.13, 0.25, 0.53, 0.81, 0.96, 1.0]
    zhu_lims     = [0.002, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]   # from zhu_2017_general.ini

    panels = [
        ("Landslide \u2014 Godt and others (2008)\nProportion of Area Affected",
         godt_prob, godt_lims, 0.05, False),
        ("Landslide \u2014 Nowicki and others (2014)\nProbability of any landslide",
         nowicki_prob, nowicki_lims, 0.07, True),
        ("Liquefaction \u2014 Zhu and others (2017), Model 2",
         liq_prob, zhu_lims, 0.002, True),
    ]

    hillshade = None
    if hillshade_file and os.path.exists(hillshade_file):
        hillshade = resample_to_grid(hillshade_file, lons, lats, Resampling.bilinear)

    rupture_geoms = None
    if rupture_file and os.path.exists(rupture_file):
        with open(rupture_file) as f:
            rupture_geoms = json.load(f)

    contour_geoms = None
    if contours_file and os.path.exists(contours_file):
        with open(contours_file) as f:
            contour_geoms = json.load(f)

    fig = plt.figure(figsize=(18, 6))

    for i, (title, data, lims, maskthresh, show_stats) in enumerate(panels):
        ax = fig.add_subplot(1, 3, i + 1, projection=proj)
        ax.set_extent(extent, crs=proj)
        cmap = cm.CMRmap_r.copy()
        cmap.set_bad([0, 0, 0, 0])
        dm = np.ma.masked_where((np.isnan(data)) | (data < maskthresh), data)

        # hillshade behind model overlay
        if hillshade is not None:
            hs_norm = (hillshade - np.nanmin(hillshade)) / (np.nanptp(hillshade) + 1e-8)
            ax.imshow(hs_norm, extent=extent, origin="upper", transform=proj,
                      cmap="gray", vmin=0, vmax=1, zorder=1)

        norm = mcolors.BoundaryNorm(lims, cmap.N)
        im = ax.imshow(dm, extent=extent, origin="upper", transform=proj,
                       cmap=cmap, norm=norm, interpolation="none", alpha=0.8, zorder=3)
        cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
        cb.set_label("Probability / Proportion", fontsize=9)

        # derived coastline
        ax.contour(LON, LAT, land_mask.astype(float), levels=[0.5],
                   colors="dimgray", linewidths=0.7, transform=proj, zorder=5)
        ocean_rgba = np.zeros((*land_mask.shape, 4))
        ocean_rgba[~land_mask] = [0.72, 0.86, 0.96, 0.5]
        ax.imshow(ocean_rgba, extent=extent, origin="upper", transform=proj, zorder=2)

        # shaking contours
        if contour_geoms:
            for feat in contour_geoms.get("features", []):
                geom = feat["geometry"]
                for coord_seq in (geom["coordinates"] if geom["type"] == "MultiLineString"
                                  else [geom["coordinates"]]):
                    xs = [c[0] for c in coord_seq]
                    ys = [c[1] for c in coord_seq]
                    ax.plot(xs, ys, "k--", linewidth=0.6, transform=proj, zorder=6)

        # finite fault
        if rupture_geoms:
            for feat in rupture_geoms.get("features", []):
                geom = feat["geometry"]
                coords = geom.get("coordinates", [])
                if geom["type"] in ("MultiLineString",):
                    for seg in coords:
                        xs = [c[0] for c in seg]
                        ys = [c[1] for c in seg]
                        ax.plot(xs, ys, "r-", linewidth=1.5, transform=proj, zorder=7)
                elif geom["type"] == "LineString":
                    xs = [c[0] for c in coords]
                    ys = [c[1] for c in coords]
                    ax.plot(xs, ys, "r-", linewidth=1.5, transform=proj, zorder=7)

        # epicenter
        ax.plot(epi_lon, epi_lat, "*", mec="k", mfc="none", mew=1.2, ms=14,
                transform=proj, zorder=10)

        # summary stats for preferred models (Nowicki, Zhu)
        if show_stats:
            mx, pct = panel_stats(data, maskthresh)
            stats_txt = f"Max P: {mx:.3f}\nArea >threshold: {pct:.1f}%"
            ax.text(0.02, 0.02, stats_txt, transform=ax.transAxes,
                    fontsize=7, va="bottom", ha="left",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, pad=0.3))

        gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="gray", alpha=0.6)
        gl.top_labels = False
        gl.right_labels = False
        gl.xlabel_style = {"fontsize": 7}
        gl.ylabel_style = {"fontsize": 7}
        ax.set_title(title, fontsize=10)

    timestr = event_meta["event_timestamp"][:10]
    suptitle = "M%.1f %s v%s - %s \u2014 Ground Failure" % (
        event_meta["magnitude"], timestr, event_meta["shakemap_version"],
        event_meta["description"])
    fig.suptitle(suptitle, fontsize=12)
    plt.tight_layout()
    plt.subplots_adjust(top=0.84)
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    print("Saved: %s" % outfile)


DEFAULT_FILENAMES = {
    "cohesion": "global_cohesion_10i_kPa.flt",
    "friction": "global_friction_deg.flt",
    "cti": "global_cti_fil.grd",
    "vs30": "global_vs30_mps.grd",
    "precip": "global_precip_fil_mm.grd",
    "wtd": "global_wtd_fil_na_m.grd",
    "dc": "global_dc_km.tif",
    "dr": "global_dr_km.grd",
}
DEFAULT_SLOPE_SUBDIR = "global_Verdin_slopes_resampled_degx100"


def resolve_path(explicit, datadir, default_name, label):
    if explicit is not None:
        return explicit
    if datadir is None:
        raise SystemExit("Missing --%s and no --datadir given." % label)
    candidate = os.path.join(datadir, default_name)
    if not os.path.exists(candidate):
        raise SystemExit("--%s not given and default not found at: %s" % (label, candidate))
    return candidate


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shakefile", required=True)
    p.add_argument("--datadir", default=None)
    p.add_argument("--slope-dir", default=None)
    p.add_argument("--cohesion", default=None)
    p.add_argument("--friction", default=None)
    p.add_argument("--cti", default=None)
    p.add_argument("--vs30", default=None)
    p.add_argument("--precip", default=None)
    p.add_argument("--wtd", default=None)
    p.add_argument("--dc", default=None)
    p.add_argument("--dr", default=None)
    p.add_argument("--outfile", default="groundfailure_map.png")
    p.add_argument("--rupture", default=None, help="Path to rupture.json (ShakeMap products)")
    p.add_argument("--contours", default=None, help="Path to a ShakeMap contour GeoJSON (e.g. cont_mmi.json)")
    p.add_argument("--hillshade", default=None, help="Path to a hillshade raster (optional)")
    p.add_argument("--thick", type=float, default=2.4)
    p.add_argument("--uwt", type=float, default=15.7)
    p.add_argument("--codiv", type=float, default=10.0)
    p.add_argument("--nodata-cohesion", type=float, default=1.0)
    p.add_argument("--nodata-friction", type=float, default=26.0)
    p.add_argument("--fsthresh", type=float, default=1.01)
    p.add_argument("--acthresh", type=float, default=0.05)
    p.add_argument("--dnthresh", type=float, default=5.0)
    p.add_argument("--slopemin", type=float, default=0.01)
    p.add_argument("--minpga", type=float, default=2.0)
    args = p.parse_args()

    for key in DEFAULT_FILENAMES:
        if getattr(args, key.replace("-", "_")) is None:
            setattr(args, key, resolve_path(None, args.datadir, DEFAULT_FILENAMES[key], key))
        else:
            setattr(args, key, getattr(args, key))

    args.cohesion = resolve_path(args.cohesion, args.datadir, DEFAULT_FILENAMES["cohesion"], "cohesion")
    args.friction = resolve_path(args.friction, args.datadir, DEFAULT_FILENAMES["friction"], "friction")
    args.cti = resolve_path(args.cti, args.datadir, DEFAULT_FILENAMES["cti"], "cti")
    args.vs30 = resolve_path(args.vs30, args.datadir, DEFAULT_FILENAMES["vs30"], "vs30")
    args.precip = resolve_path(args.precip, args.datadir, DEFAULT_FILENAMES["precip"], "precip")
    args.wtd = resolve_path(args.wtd, args.datadir, DEFAULT_FILENAMES["wtd"], "wtd")
    args.dc = resolve_path(args.dc, args.datadir, DEFAULT_FILENAMES["dc"], "dc")
    args.dr = resolve_path(args.dr, args.datadir, DEFAULT_FILENAMES["dr"], "dr")

    if args.slope_dir is None:
        if args.datadir is None:
            raise SystemExit("Missing --slope-dir and no --datadir given.")
        candidate = os.path.join(args.datadir, DEFAULT_SLOPE_SUBDIR)
        args.slope_dir = candidate if os.path.isdir(candidate) else args.datadir
        print("Using slope-dir: %s" % args.slope_dir)

    shake = parse_shakemap_grid(args.shakefile)
    lons, lats = shake["lons"], shake["lats"]
    print("Computing Godt (2008)...")
    godt_prob = compute_godt2008(
        lons, lats, shake["pga"], args.slope_dir, args.cohesion, args.friction,
        thick=args.thick, uwt=args.uwt, codiv=args.codiv,
        nodata_cohesion=args.nodata_cohesion, nodata_friction=args.nodata_friction,
        fsthresh=args.fsthresh, acthresh=args.acthresh,
        dnthresh=args.dnthresh, slopemin=args.slopemin,
    )
    print("Computing Nowicki (2014)...")
    slope_max_file = os.path.join(args.slope_dir, "slope_max.bil")
    nowicki_prob = compute_nowicki2014(
        lons, lats, shake["pgv"], slope_max_file, args.friction, args.cti,
        minpga=args.minpga, nodata_friction=args.nodata_friction,
    )
    print("Computing Zhu (2017)...")
    liq_prob = compute_zhu2017(
        lons, lats, shake["pgv"], args.vs30, args.precip, args.wtd, args.dc, args.dr,
    )
    land_mask = derive_land_mask(lons, lats, args.friction)

    plot_three_panel(lons, lats, godt_prob, nowicki_prob, liq_prob,
                     land_mask, shake, args.outfile,
                     rupture_file=args.rupture,
                     contours_file=args.contours,
                     hillshade_file=args.hillshade)


if __name__ == "__main__":
    main()
