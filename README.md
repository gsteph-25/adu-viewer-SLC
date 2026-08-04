# ADU Buildout Viewer

A single-page MapLibre GL JS app: classified raster underneath, parcel
boundaries colored by ADU potential on top, address search on top of that.
No server, no API keys, no per-request billing — everything free to run and host.

## What's in here right now

The app is currently wired to **sample data** (48 fake parcels near downtown
Salt Lake City, using the real field schema) so you can open it and see the
whole interaction working immediately — raster overlay, colored parcels,
address search, popup card.

```
adu-viewer/
├── index.html              # the whole app (map, search, styling, JS)
├── make_sample_data.py     # generated the sample data — ignore once you have real data
├── prepare_data.ipynb      # <- run this to convert YOUR shapefile + raster
├── data/
│   ├── parcels.geojson     # sample parcels — will be overwritten by prepare_data.ipynb
│   ├── raster_overlay.png  # sample classified raster — same
│   └── raster_bounds.json  # georeferencing corners for the raster
└── README.md
```

**Field schema** (matches the cleaned `SLC_Parcels_ADU_Potential_Landcover`
shapefile/GeoPackage): `PARCEL_ID`, `PARCEL_ADD`, `ZONING`, `ZONING_NAM`,
`District`, `ADU_yn`, `MinADUSpace`, `ADU_backParking`, `InTransit`, and six
land-cover sqft fields (`BuildingSqft`, `GrassSqft`, `PavedSqft`, `SoilSqft`,
`TreeSqft`, `WaterSqft`). The map colors parcels by `ADU_yn` (green =
eligible, red = not), and the raster overlay uses the same 6-class palette.

**Basemap**: [OpenFreeMap](https://openfreemap.org/) (positron style, free,
no API key), with the required attribution built into the page footer.

## 1. See it running now

Browsers block `fetch()` of local files over `file://`, so serve the folder:

```bash
cd adu-viewer
python3 -m http.server 8000
```

Open `http://localhost:8000`. Try typing "Ramona" or "900 East" in the search box.

## 2. Swap in your real data

1. Open `prepare_data.ipynb` in Jupyter and check the `Config` cell:
   - `PARCEL_SOURCE` → path to your `SLC_Parcels_ADU_Potential_Landcover.gpkg`
     (uses the GeoPackage, not the `.shp`, since several field names get
     truncated to 10 characters in a shapefile's `.dbf`)
   - `RASTER_TIF` → path to your classified raster
2. Run the notebook top to bottom:
   ```bash
   pip install geopandas rasterio pillow numpy matplotlib --break-system-packages
   ```
   It reads raster metadata only at first (instant, no memory cost regardless
   of raster size), then uses a **decimated read** (`Resampling.mode`) to pull
   a downsampled, GDAL-resampled version directly — never loading the full
   native-resolution array into memory. This matters: a citywide raster at
   fine NAIP/LiDAR resolution read at full size can be several GB and will
   silently crash a Jupyter kernel (the OS just kills the process — no Python
   traceback, which is what the `ExitCode: undefined` in VS Code's log meant).
   `MAX_OUTPUT_DIM` in the config controls the decimated size; 5000px is a
   reasonable default and already matches what an `image` overlay can usefully
   show in a browser anyway (see the scaling note in section 5 below).
3. Confirm `CLASS_BAND` and `CLASS_COLORS` in the notebook match what the
   inspection cell printed — the defaults assume classes 1–6 map to
   Building/Grass/Paved/Soil/Tree/Water in that order.
4. This overwrites `data/parcels.geojson`, `data/raster_overlay.png`, and
   `data/raster_bounds.json` with your real data, reprojected to EPSG:4326.
5. In `index.html`, update the map's initial `center` (in the
   `new maplibregl.Map({...})` call) — the notebook prints the correct center
   coordinates for your study area in the parcel export step.
6. Refresh the browser.

## 3. How address search works

Two-tier, in this priority order:
1. **Local match** — searches the `address` field already in your parcel
   attribute table. Instant, free, and exact — this is the primary path and
   is why pulling a real site-address column into the shapefile matters.
2. **Fallback geocoding** — if there's no local match, it calls the free
   [US Census Geocoder](https://geocoding.geo.census.gov) (no API key needed)
   to get coordinates, then does a point-in-polygon test against your parcels
   with turf.js to find the matching one. Useful if your parcels don't carry
   addresses, or someone types an address slightly differently than your data.

## 4. Deploying the link

Any static host works since there's no backend:

- **GitHub Pages** (free): push this folder to a repo, enable Pages on the
  `main` branch, done. `https://yourusername.github.io/repo-name/`
- **Netlify** (free): drag the folder onto [app.netlify.com/drop](https://app.netlify.com/drop) — gives you a link in seconds, no account strictly required.
- **Vercel**: similar, `vercel deploy` from the folder.

Any of these gives you the shareable link with no login required on the
viewer's end.

## 5. If your dataset is much bigger

This setup (GeoJSON + single PNG image overlay) comfortably handles a
neighborhood-to-small-city scale project — thousands of parcels, a raster a
few thousand pixels per side. If you're covering a full county or region:

- **Parcels**: convert to vector tiles with `tippecanoe` or bundle as a single
  [PMTiles](https://protomaps.com/docs/pmtiles) file instead of raw GeoJSON —
  keeps the browser from loading every parcel in one request.
- **Raster**: convert to a Cloud Optimized GeoTIFF and serve as actual raster
  tiles (e.g. `gdal2tiles.py` for static PNG tiles, or a small
  [TiTiler](https://developmentseed.org/titiler/) instance) instead of one
  giant image overlay — MapLibre's `image` source doesn't scale well past a
  few thousand pixels per side.

Happy to help with either of those conversions once you know your actual data
volume.
