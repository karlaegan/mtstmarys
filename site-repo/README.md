# Mount Saint Mary's Cemetery website

Shackleford, Saline County, Missouri. This repository holds the cemetery's
records, the code that turns them into a website, and the website itself.

The public site has three pages: a map of every lot on the aerial photo, a plat
drawing that matches the paper maps in the board's binder, and a printable
stake-out sheet for any single lot.

---

## For the board

### Where things live

| Folder | What is in it |
|---|---|
| `data/` | A copy of the records: `lots.csv`, `people.csv`, `sections.csv`, `monuments.csv`, `changes.csv`, plus the lot and section shapes (`lots.geojson`, `sections.geojson`) and `georef.json`. This is the fallback if the Google Sheet cannot be read, and it is the example of the correct format. |
| `build/` | `build.py`, the program that makes the website, its `config.json`, the page templates, and a vendored copy of Leaflet. |
| `docs/` | The website itself. This folder is what visitors see. Do not edit it by hand; it is rewritten every build. |
| `docs-private/` | The board build: the same pages but with purchaser, price, paid and board notes left in. Made only when you ask for it, never uploaded, and ignored by git. |
| `.github/workflows/` | The instructions GitHub follows to rebuild and publish the site. |

### How to edit a record

Edit the Google Sheet, not the files here. The sheet is the system of record.

* **Lots** tab: one row per lot, keyed by `lot_id` (`A-1`, `F-134`, `K-21`).
  Set `status` to open, sold, occupied, reserved, unusable or unknown.
* **People** tab: one row per burial or memorial, with its `lot_id`.
* **Sections** tab: the block layout. It rarely changes.
* **Monuments** tab: survey monuments. It holds two EXAMPLE rows today. Delete
  those once real monuments are set, and the stake-out sheets will start
  showing distances from them.
* **Changes** tab: the append-only log. A Google Form writes to it. Never edit
  or delete a row there.

Two rules the build enforces, so a mistake fails loudly instead of quietly:
`burial_count` on a lot must equal the number of People rows on it, and a lot
counts as `occupied` exactly when it has People rows.

### How the site updates

GitHub rebuilds and republishes the site on its own: twice a day, and again
whenever anything in this repository changes. You can also force a rebuild by
hand: open the **Actions** tab, choose **Build and publish the cemetery site**,
and press **Run workflow**. A run takes a couple of minutes.

Each run also commits the regenerated `docs/data/public.json` back to the
repository, so the history of the file is the history of the records.

### What the public never sees

The public build strips `purchaser`, `year_sold`, `price`, `paid`, board
`notes`, `updated_by` and `updated_on`, and it leaves out the Changes log
entirely. Lot status is collapsed to three words: **open**, **taken** or
**unusable**. Everything the board needs to see is still in the board build in
`docs-private/`, which stays on your own computer.

### Reporting a correction

The About page carries a mailto: link with a placeholder address. Replace
`BOARD-EMAIL@example.org` in `build/templates/about.html` with the board's real
address, then rebuild.

---

## For a developer

### Run the build locally

Python 3.11, and `requests` only if you build from the sheet.

```
python3 -m pip install requests        # optional, only for source = sheet
python3 build/build.py                 # public site into docs/
python3 build/build.py --private       # board build into docs-private/
python3 data/validate.py               # the data checks on their own
```

Then serve the site and open it in a browser. It must be served over http;
opening the files directly will not work, because the pages fetch their data.

```
python3 -m http.server -d docs 8000    # then visit http://localhost:8000/
```

### Point the build at the Google Sheet

In the sheet, use **File, Share, Publish to web**, choose one tab, choose
**Comma-separated values (.csv)**, and copy the link. Do that for each of the
four tabs, then put the links in `build/config.json`:

```json
{
  "source": "sheet",
  "sheet_csv_urls": {
    "Lots": "https://docs.google.com/spreadsheets/d/e/…&gid=0&single=true&output=csv",
    "People": "…",
    "Sections": "…",
    "Monuments": "…"
  },
  "site_title": "Mount Saint Mary's Cemetery",
  "public": true
}
```

With `"source": "local"` the build reads `data/` and ignores the URLs. With
`"source": "sheet"` it downloads all four, and if any download fails it prints
a loud warning and falls back to the copy in `data/` for that tab, so a
publishing hiccup at Google never takes the site down.

### Enable GitHub Pages once

In the repository: **Settings**, then **Pages**, then set **Source** to
**GitHub Actions**. Nothing else. There is no `gh-pages` branch; the workflow
uploads `docs/` as a Pages artifact and deploys it.

### Add a custom domain

There is deliberately no `docs/CNAME` file. To use a domain such as
`mtstmaryscemetery.org`, add a file named `CNAME` inside `docs/` containing
just the domain on one line, add it to the repository, then enter the same
domain under **Settings, Pages, Custom domain** and set the DNS records GitHub
shows you. Because `docs/` is rewritten by every build, also copy the file into
`build/templates/` and add it to the copy list in `build.py` so it survives.

### When the survey arrives

Only the two GeoJSON files depend on the paper geometry, so a survey drops in
cleanly:

1. Produce polygons keyed by the same `lot_id` values, with
   `properties.geometry_source` set to `"survey"`.
2. Replace `data/lots.geojson` (and `data/sections.geojson` if the block
   corners were surveyed), and set `geometry_source` to `survey` on those rows
   in the Lots sheet.
3. Record the real monuments in the Monuments sheet and delete the EXAMPLE
   rows. The stake-out sheets pick up the distance table automatically.
4. If the surveyor gives State Plane values, add a `state_plane` block to
   `data/georef.json` with `epsg`, `name`, and a `reference` point
   (`lat`, `lon`, `northing_ft`, `easting_ft`). The stake-out sheets then print
   northing and easting beside latitude and longitude.
5. Run `python3 data/validate.py`. It fails if any lot loses its polygon or a
   polygon has no lot, so a partial survey file cannot quietly drop lots.
6. Note the change in the Changes tab.

### What the build writes

`docs/data/public.json` (one record per lot: id, section, lot number, collapsed
status, corner bounds, dimensions, neighboring lot ids, and the people on it),
`docs/data/monuments.json`, and the four pages from `build/templates/`.
Templates carry the placeholders `{{SITE_TITLE}}`, `{{GENERATED}}`,
`{{DATA_FILE}}` and `{{BUILD_KIND}}`.

### Map library

The map page loads Leaflet 1.9.4 from cdnjs, and falls back to the copy in
`build/vendor/leaflet/` (copied to `docs/vendor/leaflet/` by the build) if the
CDN cannot be reached. Nothing else is loaded from anywhere: no analytics, no
trackers.

### Accuracy

The lot shapes come from the column widths on the paper section maps, anchored
at one point, the northwest inside corner of the loop drive. Absolute position
is good to roughly 10 to 20 feet; the spacing between lots is better than that.
Every page says so. Do not use these shapes to open a grave or settle a
boundary.

### License

MIT, see `LICENSE`. Author: Mount Saint Mary's Cemetery Board. No analytics and
no trackers are used anywhere on the site.
