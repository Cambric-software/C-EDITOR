# C EDITOR

An offline creative and productivity suite for Windows. One desktop application with six
departments: documents, design, spreadsheet, slides, video and animation.

Everything runs locally on your computer. No account, subscription or internet connection is
required for editing, and your files never leave your machine.

## Departments

- **Documents** — rich-text editor with styles, tables, images, page breaks, headers and footers,
  page numbers, table of contents, footnotes and endnotes, bookmarks, cross-references, track
  changes, comments, mail merge, proofreading, document comparison, document statistics, find and
  replace, change case, line sorting, and PDF/HTML/TXT/DOCX/SVG export.
- **Design** — drag-and-drop canvas with rectangles, rounded rectangles, ellipses, triangles,
  stars, pentagons, hexagons, diamonds, lines, arrows, text and images. Multi-select, grouping,
  layer ordering, locking, alignment, snapping and guides, object rotation, image brightness/
  contrast/blur, brand kit, templates, and PNG/JPEG/WebP/SVG export.
- **Spreadsheet** — multi-sheet grid with formulas (SUM, AVERAGE, COUNT, MAX, MIN, MEDIAN, STDEV,
  IF, IFERROR, VLOOKUP, INDEX, MATCH, SUMPRODUCT, COUNTIF, SUMIF, COUNTIFS, text functions, date
  functions and arithmetic), named ranges, data validation, conditional formatting, pivot tables,
  row filtering, column sorting, freeze panes, cell formats, charts (bar, stacked bar, line, area,
  pie, doughnut, scatter), and CSV import/export.
- **Slides** — layouts, themes, slide master, sections, speaker notes, slide sorter, per-slide
  transitions, and a full-screen presenter with fade, slide, zoom and typewriter animation.
- **Video** — multi-track timeline with trimming, splitting, duplicating, speed, volume, fades,
  filters, colour grading, crossfade/slide/zoom transitions, title tracks, captions, SRT export and
  MP4 rendering. Audio-track clips are mixed into the final render.
- **Animation** — frame-by-frame studio with layers, onion skin, brush, pencil, line, arrow,
  rectangle, rounded rectangle, ellipse, star, polygon, fill, text and eraser tools, filled shapes,
  frame copy/paste/insert/reverse, playback, export effects, and GIF/PNG-sequence/MP4 export.
- **Creations** — gallery of files you have created, with open, delete, copy path and export actions.

## Requirements

- Windows 10 or later
- Python 3.10 or later
- Optional: `ffmpeg` on `PATH` for MP4 video and animation rendering
- Optional: `Pillow` for PNG/JPEG/WebP design and animation export
- Optional: `python-docx`, `python-pptx`, `openpyxl`, `reportlab` for the matching import/export
  formats; the app reports clearly when a package is missing

## Run

```bash
python run_c_editor.py
```

or double-click `C_Editor.bat`.

The first launch offers to install a desktop shortcut. Projects are saved as `.hds` (documents),
`.hvs` (video) and `.json` (design) files, plus the format-specific exports listed above.

## Verify

```bash
python -m py_compile c_editor.py
python smoke_test.py
```

The smoke suite prints `25 core-suite smoke passes: OK`.

## Project layout

- `c_editor.py` — the desktop application
- `suite_core.py` — shared project models and serialisation helpers
- `creative_departments.py` — creative helpers and department content
- `assets/` — icons, logo and bundled template artwork
- `docs/` — user and architecture documentation
- `app/` — early Flutter scaffold, not part of the shipped desktop build

## Documentation

See `docs/` for the feature reference, architecture notes and build instructions.

## License

Proprietary. See `LICENSE`. Security policy: `SECURITY.md`.
