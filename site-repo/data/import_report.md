# Import report - 2026-09-04

Source files: `list_of_names.csv` (board sheet, Sections A-C), `final/A.csv`..`final/H.csv` (arbitrated paper transcriptions), the newer lettered field as transcribed in `pass1/newer_sections_geometry.md` (read from its machine form in the plat's DATA blob), `final/ABC_crosscheck.xlsx`, and `plots_sold.csv`.

## Table counts

| Table | Rows |
|---|---|
| lots.csv | 2610 |
| people.csv | 910 |
| sections.csv | 23 |
| monuments.csv | 2 (both EXAMPLE) |
| changes.csv | 1 (import note) |
| lots.geojson | 2610 features |
| sections.geojson | 23 features |

## Per section

| Section | Lots | People | Occupied | Sold | Unusable | Open |
|---|---|---|---|---|---|---|
| A | 180 | 80 | 76 | 0 | 0 | 104 |
| B | 160 | 75 | 59 | 0 | 0 | 101 |
| C | 220 | 136 | 119 | 0 | 6 | 95 |
| D | 180 | 76 | 68 | 0 | 11 | 101 |
| E | 160 | 113 | 102 | 0 | 1 | 57 |
| F | 160 | 119 | 111 | 0 | 1 | 48 |
| G | 180 | 112 | 109 | 0 | 10 | 61 |
| H | 170 | 132 | 128 | 0 | 0 | 42 |
| I | 80 | 11 | 11 | 0 | 0 | 69 |
| J | 80 | 6 | 6 | 0 | 0 | 74 |
| K | 80 | 6 | 6 | 0 | 0 | 74 |
| L | 80 | 5 | 5 | 0 | 0 | 75 |
| M | 80 | 4 | 4 | 0 | 0 | 76 |
| N | 80 | 5 | 5 | 0 | 2 | 73 |
| O | 80 | 6 | 6 | 1 | 0 | 73 |
| P | 80 | 8 | 7 | 3 | 1 | 69 |
| Q | 80 | 2 | 2 | 4 | 0 | 74 |
| R | 80 | 6 | 6 | 0 | 0 | 74 |
| S | 80 | 2 | 2 | 0 | 2 | 76 |
| T | 80 | 6 | 6 | 0 | 0 | 74 |
| U | 80 | 0 | 0 | 0 | 0 | 80 |
| V | 80 | 0 | 0 | 0 | 0 | 80 |
| W | 80 | 0 | 0 | 0 | 0 | 80 |
| **Total** | 2610 | 910 | 838 | 8 | 34 | 1730 |

## Sections A-C merge (sheet vs paper)

| Case | People rows |
|---|---|
| Agree (source `paper+sheet`) | 169 |
| Disagree - sheet name kept, paper reading in note, confidence medium | 64 |
| Sheet only (source `sheet`) | 5 |
| Paper only (source `paper`, paper confidence) | 36 |
| Sheet data-entry defects repaired from the paper split | 17 |

The repaired rows are Section C plots 6, 11, 14, 28, 31, 92, 140 and 158 (two people crammed into the sheet's First/Last columns) and C 202 (first and last name swapped). Each carries the reason in its `note`.

## Rows that could not be placed

None. Every sheet name, paper row and ledger row landed on a lot that exists in the section grids.

## Assumptions and discrepancies worth the board's attention

- **Section E and F lot counts.** DATA_MODEL.md lists E and F as 180 lots each. The paper number grids (p-16, p-19), the pass-1 geometry notes and the current plat all show 8 columns of 20 = **160 lots** for both, and no paper row, sheet row or ledger row anywhere references E or F above 160. The tables therefore carry 160 lots for E and 160 for F. If the board knows of a ninth column in either section, it needs a page that shows it.
- The board sheet covers Section B only to plot 140; B 141-160 exist on the paper grid and are carried here as `open`.
- Section H lots 161-170 are a later 5 ft strip on the west edge that is not on the number grid; they are drawn in the northernmost 10 rows.
- Newer-field people and marks come from the transcription of p-31 to p-43; rows 41-80 are empty except two marked trees at row 61.
- Georeferencing: see `georef.json`. Anchor derived from the Find a Grave published point 39.13670 / -93.30580, assumed to be the centre of the mapped area. Absolute accuracy 10-20 ft.
