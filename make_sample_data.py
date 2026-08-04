"""
Generates SAMPLE data standing in for the user's real ADU classified raster +
parcel shapefile, so the viewer works end-to-end before real data is dropped in.

Output:
  data/parcels.geojson       - synthetic parcels w/ ADU buildout attributes
  data/raster_overlay.png    - synthetic classified raster (RGBA PNG)
  data/raster_bounds.json    - [[lon,lat] x4] corners for MapLibre image source
"""
import json
import random
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, mapping

random.seed(7)
np.random.seed(7)

# Rough downtown Salt Lake City grid — swap for your real study area
ORIGIN_LON, ORIGIN_LAT = -111.8910, 40.7608
COLS, ROWS = 8, 6
PARCEL_W, PARCEL_H = 0.00055, 0.00040   # degrees, ~ a city-block-ish lot
GAP = 0.00006                            # street/alley gap between parcels

STREETS = ["Ramona Ave", "Windsor St", "800 East", "900 East", "Blaine Ave", "Wilmington Ave"]

features = []
class_grid_rows = []  # per-parcel raster class grids, assembled into full raster later

for r in range(ROWS):
    for c in range(COLS):
        x0 = ORIGIN_LON + c * (PARCEL_W + GAP)
        y0 = ORIGIN_LAT - r * (PARCEL_H + GAP)
        x1, y1 = x0 + PARCEL_W, y0 - PARCEL_H

        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])

        lot_sqft = round(PARCEL_W * PARCEL_H * (111320 ** 2) * np.cos(np.radians(ORIGIN_LAT)))
        # vary land cover coverage per parcel across the 6 real classes
        building_pct = np.clip(np.random.normal(0.26, 0.07), 0.10, 0.50)
        paved_pct = np.clip(np.random.normal(0.12, 0.05), 0.02, 0.30)
        soil_pct = np.clip(np.random.normal(0.05, 0.03), 0.0, 0.15)
        water_pct = 0.0 if np.random.random() > 0.08 else np.clip(np.random.normal(0.03, 0.02), 0.0, 0.08)
        tree_pct = np.clip(np.random.normal(0.10, 0.05), 0.0, 0.25)
        grass_pct = max(1 - building_pct - paved_pct - soil_pct - water_pct - tree_pct, 0.05)

        building_sqft = round(lot_sqft * building_pct)
        paved_sqft = round(lot_sqft * paved_pct)
        soil_sqft = round(lot_sqft * soil_pct)
        water_sqft = round(lot_sqft * water_pct)
        tree_sqft = round(lot_sqft * tree_pct)
        grass_sqft = round(lot_sqft * grass_pct)

        available_sqft = max(lot_sqft - building_sqft - paved_sqft - water_sqft - 400, 0)  # 400 = setback/access buffer
        min_adu_space = 400  # typical minimum footprint needed for a detached ADU
        adu_eligible = "Y" if available_sqft >= min_adu_space else "N"

        addr = f"{1200 + r*100 + c*10} {STREETS[(r + c) % len(STREETS)]}, Salt Lake City, UT"
        zoning = random.choice(["R-1-5000", "R-1-7000", "SR-1A"])

        features.append({
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": {
                "PARCEL_ID": f"P-{r:02d}{c:02d}",
                "PARCEL_ADD": addr,
                "ZONING": zoning,
                "ZONING_NAM": zoning.replace("-", " "),
                "District": f"District {(r % 3) + 1}",
                "BuildingSqft": building_sqft,
                "GrassSqft": grass_sqft,
                "PavedSqft": paved_sqft,
                "SoilSqft": soil_sqft,
                "TreeSqft": tree_sqft,
                "WaterSqft": water_sqft,
                "MinADUSpace": min_adu_space,
                "ADU_yn": adu_eligible,
                "ADU_backParking": "Y" if np.random.random() > 0.4 else "N",
                "InTransit": "Y" if np.random.random() > 0.6 else "N",
            }
        })

geojson = {"type": "FeatureCollection", "features": features}
with open("data/parcels.geojson", "w") as f:
    json.dump(geojson, f)

# --- synthetic classified raster, aligned to the same grid extent ---
PX_PER_PARCEL = 40
img_w = COLS * PX_PER_PARCEL
img_h = ROWS * PX_PER_PARCEL

# class colors, matching CLASS_LABELS in prepare_data.ipynb: 1 building, 2 ILV/grass, 3 impervious, 4 NLV/soil, 5 trees, 6 water
palette = {
    1: (255, 0, 0, 255),      # building/structure - red
    2: (0, 255, 0, 255),      # ILV (grass/lawn) - bright green
    3: (0, 0, 0, 255),        # impervious (asphalt/concrete) - black
    4: (153, 140, 86, 255),   # NLV/soil - tan/olive
    5: (34, 102, 34, 255),    # trees - dark green
    6: (0, 0, 255, 255),      # water - blue
}

arr = np.zeros((img_h, img_w, 4), dtype=np.uint8)

for r in range(ROWS):
    for c in range(COLS):
        feat = features[r * COLS + c]["properties"]
        lot = feat["BuildingSqft"] + feat["GrassSqft"] + feat["PavedSqft"] + feat["SoilSqft"] + feat["TreeSqft"] + feat["WaterSqft"]
        building_frac = feat["BuildingSqft"] / lot
        paved_frac = feat["PavedSqft"] / lot
        soil_frac = feat["SoilSqft"] / lot
        water_frac = feat["WaterSqft"] / lot

        y0, x0 = r * PX_PER_PARCEL, c * PX_PER_PARCEL
        block = np.full((PX_PER_PARCEL, PX_PER_PARCEL), 2, dtype=np.uint8)  # default grass

        n_building = int(building_frac * PX_PER_PARCEL * PX_PER_PARCEL)
        n_paved = int(paved_frac * PX_PER_PARCEL * PX_PER_PARCEL)
        n_soil = int(soil_frac * PX_PER_PARCEL * PX_PER_PARCEL)
        n_water = int(water_frac * PX_PER_PARCEL * PX_PER_PARCEL)

        # building footprint: solid block in one corner
        bh = int(np.sqrt(n_building * 1.4))
        bw = max(1, n_building // max(bh, 1))
        bh = min(bh, PX_PER_PARCEL - 4)
        bw = min(bw, PX_PER_PARCEL - 4)
        block[2:2+bh, 2:2+bw] = 1

        # driveway strip: paved along one edge
        strip_w = max(1, n_paved // PX_PER_PARCEL)
        block[:, PX_PER_PARCEL - strip_w:] = 3

        # patch of bare soil along the bottom edge
        soil_h = max(0, n_soil // PX_PER_PARCEL)
        if soil_h:
            block[PX_PER_PARCEL - soil_h:, :PX_PER_PARCEL - strip_w] = 4

        # rare water feature (small pond/pool corner)
        if n_water > 4:
            wh = max(1, int(np.sqrt(n_water)))
            block[PX_PER_PARCEL - wh - soil_h:PX_PER_PARCEL - soil_h, :wh] = 6

        # scatter a few tree canopy pixels in the grass area
        grass_mask = (block == 2)
        n_trees = int(grass_mask.sum() * 0.15)
        grass_idx = np.argwhere(grass_mask)
        if len(grass_idx) and n_trees:
            pick = grass_idx[np.random.choice(len(grass_idx), size=min(n_trees, len(grass_idx)), replace=False)]
            for (yy, xx) in pick:
                block[yy, xx] = 5

        for cls, color in palette.items():
            arr[y0:y0+PX_PER_PARCEL, x0:x0+PX_PER_PARCEL][block == cls] = color

Image.fromarray(arr, mode="RGBA").save("data/raster_overlay.png")

# raster corner bounds matching the full parcel grid extent, [lon,lat] TL,TR,BR,BL (MapLibre image source order)
top_lat = ORIGIN_LAT
bottom_lat = ORIGIN_LAT - ROWS * (PARCEL_H + GAP) + GAP
left_lon = ORIGIN_LON
right_lon = ORIGIN_LON + COLS * (PARCEL_W + GAP) - GAP

bounds = [
    [left_lon, top_lat],     # top-left
    [right_lon, top_lat],    # top-right
    [right_lon, bottom_lat], # bottom-right
    [left_lon, bottom_lat],  # bottom-left
]
with open("data/raster_bounds.json", "w") as f:
    json.dump(bounds, f)

print(f"Generated {len(features)} parcels, raster {img_w}x{img_h}px")
print("center for map fly-to:", (ORIGIN_LON + right_lon) / 2, (ORIGIN_LAT + bottom_lat) / 2)
