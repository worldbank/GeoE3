# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version policy: the version here and in `config.json`/`geest/metadata.txt`
stays exactly one semver step ahead of the last version actually tagged
and released on GitHub - never bumped again per commit after that. All
work since the last release accumulates under that single pending
version (upgrading patch->minor->major in place if a later change needs
a bigger bump) until a release is cut and tagged, at which point the next
single step begins.

## [Unreleased]

## [2.1.1] - 2026-11-12

Everything below accumulated on top of the last tagged release, v2.0.6;
none of it has been released yet, so it is kept under this single pending
version per the policy above.

### Added

- The "Factor Correlations" insights page now explains how to read its
  heatmap: a "How to read this grid" caption covering the numbered
  row/column key and what the diagonal means, plus a diverging
  colour-scale bar (red -1 / white 0 / navy +1) with tick labels -
  the colours alone didn't say which direction was good or what the
  diagonal represented. `AnalysisReport._draw_correlation_scale_bar()`;
  `_draw_correlation_heatmap()` now returns its bottom y-coordinate so
  the caller can place the new block directly beneath it without
  duplicating the layout geometry.
- A new "How Scores Combine" diagram augments the Methodology section's
  own intro page (not a page of its own) and traces a score from a
  single indicator all the way up to the four published products:
  indicator -> factor -> dimension -> GeoE3 Score (each step a weighted
  sum, labelled with the actual `factor_weighting`/`dimension_weighting`/
  `analysis_weighting` model.json attributes), then the total filtered
  two independent ways - by population tercile and by the opportunities
  mask - to produce "GeoE3 score", "By population", "GHSL masked" and
  "By population (GHSL)". The two filters sit level with the GeoE3
  Score box rather than up near the funnel's top, so the two feed
  arrows run as clean right angles instead of diagonals crossing
  through the "every other used factor/dimension" ghost notes above;
  the "both filters" lane merges into a single trunk just below the
  filter boxes instead of running as two parallel lines the full page
  height. New `geest/resources/methodology/scoring_pipeline.svg`,
  folded into `AnalysisReport.make_methodology_pages()`.
- A new collapsible "item info" panel sits above the tree panel's
  button row, explaining whatever dimension/factor/indicator is
  currently selected: a heading, a short description and its tree
  icon. For an indicator with a known scoring technique, a
  "Methodology →" link slides over to a second page showing the real-
  world technique behind its score - the same name, description and
  icon used on the analysis report's own Methodology pages, so the
  two stay in sync. Replaces the old map-canvas overlay
  (`LayerDescriptionItem`, deleted - it had been disabled since May
  2026 and a dock panel next to the controls the user is already
  looking at beats a floating label on the map). New
  `geest.gui.widgets.ItemInfoPanel`.
- That item info panel now shows a hand-drawn, topic-relevant icon for
  the selected dimension/factor/indicator instead of the generic tree
  role glyph (the same cube/folder/leaf icon regardless of whether the
  item was "Accessibility" or "Fire risk"). 30 new brand-aligned SVGs
  (navy `#002244` line art with one cyan `#009FDA` accent each, matching
  the report's own colour constants) cover the analysis level, all 3
  dimensions, all 16 factors and the 10 indicators that don't already
  share their parent factor's icon (the other 14 factors have exactly
  one indicator covering the same real-world topic, so factor and
  indicator intentionally share a file rather than duplicating it).
  The icon now sits inside a rounded square tile to the left of the
  heading/description text, instead of a bare unframed glyph. New
  `geest/resources/icons/topics/` and `geest.core.topic_icons`
  (`topic_icon_filename()`), falling back to the existing generic role
  icon for any item id that isn't mapped. Two icons (the bus and the
  bank) originally had one of a pair/trio of otherwise-identical shapes
  (a wheel, a column) coloured cyan while its siblings stayed navy -
  fixed so repeated shapes are always the same colour and the one cyan
  accent per icon lands on a structurally distinct element instead.
  The panel's description line also no longer falls back to
  `getItemTooltip()`, which could surface a transient run warning/error
  (e.g. "No service areas could be computed...") as if it were a
  description of the indicator - that text still shows correctly on the
  tree row's own hover tooltip, just not here. Since almost every
  indicator's own `description` in model.json is blank, the panel now
  borrows its parent factor's description instead (always populated)
  rather than showing the bare word "Indicator" with nothing after it,
  truncated the same way the methodology summary already is so a long
  borrowed description doesn't overflow the card. The bicycle icon's
  frame didn't reach the centre of one wheel and its cyan accent
  overlapped the wheel's rim, reading as a mis-coloured wheel - redrawn
  with a proper diamond frame that meets both hubs exactly, with the
  accent moved well clear of either wheel. The "Methodology →" link
  moved out of the card into the header row, to the left of the
  collapse/expand chevron, freeing a full line of the card's height for
  the description; the card itself grew (112px -> 140px). The header nav
  is now a true carousel: "Selected item" itself becomes a clickable
  "← Selected item" back-link on the methodology page, replacing the
  separate in-card back-link row entirely and freeing another line.
  Clicking the header bar, the header nav or the Methodology link while
  the panel is collapsed now re-expands it first, rather than being a
  dead end. The description and methodology summary are no longer
  truncated with an ellipsis at all - character-count truncation always
  left the reader hanging mid-sentence with no way to see the rest, so
  both are now scrollable read-only text areas (`QTextEdit`, not `QLabel`)
  showing the complete text, with a scrollbar appearing only when it's
  actually needed.
- The status text and the two progress bars shown during an analysis
  run, a resource download, or a report export now live inside that
  same item info panel, on their own page, instead of a separate status
  row and two fixed-width bars in the button row below - the panel
  auto-expands and its header reads "Analysis in progress...",
  "Downloading resources...", "Generating analysis report..." or
  "Generating study area report..." (whichever started it) for the
  duration, then returns to "Selected item" when it finishes. New
  `ItemInfoPanel.show_progress()`/`hide_progress()`;
  `TreePanel.overall_progress_bar`/`workflow_progress_bar`/`status_label`
  are now aliases onto the panel's own widgets, so none of the ~30
  existing call sites that update them needed to change.
- Every map in the analysis report - the large main map (inset into its
  own bottom-right corner over a translucent backing panel) and every
  minimap (dimension/factor/indicator grids, plus the GeoE3 score/
  GHSL-masked/by-population products) - now shows a small score-
  distribution sparkline, read directly from that layer's own
  `study_area_grid` column in the GeoPackage - the same values every
  result raster was rasterised from. Plain 0-5 products use a 5-bar
  likert chart matching `resources/qml/analysis.qml`'s DISCRETE boundaries
  `(0,1],(1,2],...` and colours (`SCORE_LEGEND_COLORS`); the "by
  population" bivariate product uses its own 15-bar chart matching
  `geoe3_by_population_score.qml`'s exact-value palette
  (`GEOE3_BY_POPULATION_COLORS`) instead, rather than being misread
  through the wrong 5-class scale. Score 0 (masked/excluded cells) is
  excluded from every count - it's typically the overwhelming majority of
  cells outside the populated/opportunity area, and including it would
  flatten the distribution the sparkline exists to show. Products on no
  usable scale (the binary opportunities mask) are skipped rather than
  shown with a meaningless chart. New generic `BaseReport._draw_sparkline()`
  primitive and `AnalysisReport._grid_column_score_histogram()`/
  `_grid_column_palette_histogram()`/`_draw_sparkline_for_column()`/
  `_draw_main_map_sparkline()`.
- Indicator/factor configuration dialogs' value-range|index-score mapping
  tables (the reference table shown while picking an analysis mode, e.g.
  Contextual Index Score, Street Lights, Multi/Single Buffer, Safety
  Raster, ACLED CSV, OSM Transport highway/cycleway classification) now
  show a "Legend" column with a solid colour swatch for each row, matching
  the same 5-class colour ramp (`#d7191c`→`#2c7bb6`) every result
  map/raster already uses (`resources/qml/indicator.qml`/`factor.qml`), so
  a user can see at a glance which map colour a given score corresponds to
  without cross-referencing the separate map legend. New shared
  `geest.core.constants.SCORE_LEGEND_COLORS` and
  `legend_cell_html()`/`legend_color_for_score()` helpers in
  `base_configuration_widget.py`, reused by every affected widget rather
  than hand-rolling the colour lookup per table. Left out: Safety
  Polygon's classification table (user-editable 0-100 values, not a
  read-only 1-5 score reference) and the plain Index Score widget (has no
  mapping table at all).
- `admin.py generate-zip` now bundles `h3` into the release zip by
  default (`VENDORED_PACKAGES = ["h3==4.4.2"]`), wired automatically into
  `build()` rather than requiring a separate manual `bundle-deps` step
  beforehand - the previous default (`VENDORED_PACKAGES = []`, with CI
  passing `--packages "h3==4.4.2"` as an override) meant a plain local
  `generate-zip` silently shipped a plugin that would fail to import h3
  wherever the end user's own QGIS Python doesn't already have it.
  `.github/workflows/release.yml`'s now-redundant explicit "Bundle
  dependencies" step was removed.
  Also fixed two real gaps found while verifying this: `WHEEL_PLATFORMS`
  never requested a `cp313` wheel for Windows/macOS at all (only Linux
  had it - any Windows/macOS user on QGIS 4.x, which ships Python 3.13,
  would have hit an ImportError), and macOS Intel/ARM wheels were
  silently clobbering each other at extraction time (h3 publishes no
  universal2 wheel, and macOS wheel filenames don't encode architecture
  the way manylinux's do, so both unpack to the identical path) - every
  bundled macOS `.so` was actually arm64 only despite Intel also being
  requested. `WHEEL_PLATFORMS` now targets cp312/cp313 only
  (Linux/Windows/macOS-arm64), dropping cp311/cp314 and Intel macOS -
  this was also necessary to fit under the plugin zip's 15MB hard limit
  on QGIS's plugin repository infrastructure (see below), which a
  correctly-complete bundle would otherwise have exceeded.
- `generate-zip` now refuses to produce a zip over 15MB (`MAX_ZIP_SIZE_MB`),
  QGIS's plugin repository hard limit, and always prints a small ASCII
  dashboard breaking the zip's compressed size down by top-level plugin
  area (`extlibs`, `core`, `gui`, `resources`, ...) with a bar chart, so
  it's obvious at a glance what's actually driving the size - not just
  the final pass/fail total.
- `bundle_deps()` now strips build-time-only files after extracting each
  wheel (Cython `.pyx`/`.pxd` source, C headers, static libs, CMake
  config) - never needed to just `import h3` at runtime, pure dead
  weight in every release before now.
- `admin.py`'s packaging excludes a short list of dev-only files that were
  previously swept into every release zip for no runtime benefit
  (`EXCLUDE_FILES`): `generate_model.py`/`geoe3.ods` (the
  spreadsheet-to-`model.json` tooling invoked only by
  `scripts/import-ods-to-model.sh`, never imported by the plugin itself),
  `geoe3_styling.xlsx` (a design reference, not loaded by any code),
  `ghs-mod-2023-tile-scheme.qmd` (a QGIS-authored metadata sidecar for the
  GHSL tile scheme layer, not read back - the plugin only ever loads the
  sibling `.parquet`/`.gpkg`), and `insights.model3` (an unused QGIS
  Processing model with no code reference).
- `analysis_summary_report_template.qpt`'s two picture items were
  embedding base64 copies of `geest/resources/images/geoe3-bg.png` and
  `geest/resources/geoe3-banner.png` (QGIS's own "Embedded" picture
  save mode) - byte-for-byte duplicates (confirmed via SHA256) of files
  the plugin already ships separately, inflating the template from ~20KB
  to ~3.9MB for no reason. The template's `file=` attributes now hold
  placeholder tokens (`PLUGIN_RESOURCE:...`) that
  `BaseReport.load_template()` (`geest/core/reports/base_report.py`)
  substitutes for the real resolved resource path before parsing, so the
  template file itself never needs to hardcode an absolute,
  install-location-specific path.
- The four largest shipped background PNGs
  (`geoe3-bg.png`, `geoe3-page-header-bg.png`, `geoe3-page-footer-bg.png`,
  `geoe3-page-no-bg.png`) are flat-colour illustration with a subtle
  grain texture, not photographic content, so they compress far better
  as a restricted 256-colour palette than as 8-bit-per-channel truecolor
  - re-saved as 256-colour palette PNGs (same filenames/format, no code
  changes needed) for a combined 3.75MB -> 1.14MB (~70% smaller), with
  RMSE under 0.7% against the originals (visually indistinguishable).
- Safety Perception's nighttime lights indicator can now download its own
  raster directly in-app at local/national scale (worldbank/GeoE3#452),
  following the same button/`QgsTask` pattern as the existing S2S
  downloaders. The source is the annual VIIRS nighttime lights composite
  (OpenGeoHub/Hengl mirror on Zenodo, CC-BY 4.0, 2000-2024, no login
  required - the authoritative EOG source now gates all downloads behind
  free account registration, which this avoids). The global composite
  (~60 MB) is downloaded with `QgsNetworkAccessManager`'s blocking GET
  (the same pattern `S2SClient` already uses) rather than GDAL's
  `/vsicurl/` driver reading it remotely - some network/proxy environments
  block the HTTP Range requests `/vsicurl/` needs, so a plain synchronous
  download is more portable even though it means fetching the whole file;
  cropping to the study area then happens locally. `SafetyRasterWorkflow`
  needed no changes: the download writes to the same
  `nighttime_lights_raster` attribute the manual file picker already
  populated.
- All five environmental hazard indicators (fire, flood, landslide, cyclone,
  drought) can now download their own raster directly in-app at
  local/national scale, the same button/`QgsTask` pattern as the nighttime
  lights downloader above - previously only a manual "visit the source page
  and download it yourself" link was offered. Each hazard's source is its
  direct, no-login World Bank Data Catalog (DDH) file
  (`ENV_HAZARD_DOWNLOAD_URLS` in `geest/core/constants.py`), downloaded in
  full via `QgsNetworkAccessManager`'s blocking GET and then cropped locally
  to the study area. The download/crop logic shared with the nighttime
  lights downloader was extracted into `geest.core.tasks.raster_download_utils`
  rather than duplicated. Source files range from ~3 MB (fire, cyclone) to
  ~1 GB (drought); the button warns and asks for confirmation before
  starting any download at or above 100 MB.
- New "Download all resources" option on the Run button's dropdown menu:
  walks every indicator, and for any backed by a downloadable external
  resource, checks for an existing cached file under
  `working_directory/study_area/` and downloads it only if missing, then
  sets it as that indicator's configured source - the same attribute each
  resource's own in-app "Download ..." button would write. Covers
  nighttime lights and environmental hazard rasters, and OSM-matched
  buffer-point indicators (schools, health facilities, pharmacies, grocery
  stores, financial services, kindergartens, green spaces, water points,
  public transport - the same keyword-matched categories the in-dialog
  "Download from OSM" button already offers, now extracted into
  `geest.core.osm_downloaders.resolve_point_osm_download_type` as a single
  source of truth shared by both). Unlike the raster resources, an OSM
  indicator's configured source is an actual QGIS project layer, not a
  file path - the downloaded GeoPackage is loaded and added to the
  project, then wired up via the same `{widget_key}_layer_*` attributes
  `VectorDataSourceWidget.update_attributes()` itself writes. It also
  covers environmental hazard indicators left at "Do Not Use" (the
  unconfigured default) but checked on in their factor's aggregation
  dialog - status "Required and not configured" - rather than only ones
  that already had a datasource mode explicitly picked: if such an
  indicator's id matches a known hazard type, downloading its data also
  switches its mode to "Environmental Hazard" at the same time, so it
  comes out "ready to run" instead of staying stuck on "required". While a
  download is in progress, its indicator's row shows the same animated
  throbber a normal single-indicator run already shows, and the tree view
  is refreshed via `layoutChanged` (not a full model reset) once
  downloads/wiring finish, so newly-configured indicators immediately show
  their updated status without collapsing every expanded node or losing
  the current selection/scroll position. Deliberately not covered yet
  (documented in `geest/core/download_all_resources.py`'s module
  docstring): GHSL/Ookla, transport/generic polyline/point modes, and the
  regional S2S-backed equivalents of nighttime lights/environmental
  hazards.
- `pyarrow` added to the nix dev shell (devShell tooling and the
  QGIS-bundled Python both). A benchmark comparing GeoPackage, Shapefile,
  FlatGeobuf and GeoParquet writes/reads found the file format made
  almost no difference to speed - the bottleneck was GDAL/OGR's
  per-feature Python API (`CreateFeature()`/feature iteration), not the
  on-disk format - so rather than migrate formats, the plugin's biggest
  bulk vector writes now try GDAL's columnar Arrow-batch API
  (`Layer.WritePyArrow()`) first, which got ~1.75x faster writes on the
  SAME GeoPackage files. New `geest/core/arrow_batch_writer.py` helper:
  if pyarrow isn't importable (not every QGIS install bundles it, though
  OSGeo4W's Windows installer does by default), it returns `False` and
  every call site falls straight back to its original per-feature
  `CreateFeature()` loop - no format change, no hard dependency. Wired
  into `UnifiedWriterThread._write_grid_batch`/`_write_geometry_batch`
  (`study_area_processing_task.py`) - the base study-area grid write, the
  biggest cell counts every study area creation produces.
- Separately, H3 grid generation's `bbox_to_wgs84()`/
  `transform_wgs84_to_target()` (`geest/core/h3_utils.py`) were rebuilding
  a fresh `osr.CoordinateTransformation` on every single call - and both
  run once per grid cell, tens to hundreds of thousands of times per
  study area. Benchmarked ~20-30x slower than reusing one for the same
  EPSG pair; now cached thread-locally (keyed by source/target EPSG),
  cutting H3 grid generation time roughly 4x in testing.
- Every sparkline bar in the analysis report now labels itself with its
  rounded share of the total (e.g. `52%`) directly beneath the bar - bars
  rounding to 0% are left unlabelled, avoiding a wall of meaningless
  labels on the 15-class by-population chart, where most classes are
  usually empty. New `_draw_sparkline()` `show_percentages` parameter
  (`base_report.py`, default `True`).
- The analysis report's title now carries the project's admin0 (country)
  name as a subtitle (e.g. "GeoE3 Analysis Report — Tunisia"), read from
  `study_area/boundaries_dissolved.gpkg` - the field the user chose
  during project setup to dissolve the study area boundary by. Picked out
  by field TYPE (first String field) rather than name or position, since
  GeoPackage surfaces its own integer `fid` primary key as field 0 ahead
  of whatever name column the user picked. New
  `AnalysisReport._admin0_name()`.
- The analysis report now includes a page for each of the four
  subnational aggregation vector products (GeoE3 score, GHSL-masked, by
  population, by population GHSL-masked) - the majority score within
  each administrative zone the user configured during project setup,
  previously computed but never shown in the report. New
  `AnalysisReport._add_vector_map_page()`/`_load_vector()`/
  `_read_vector_field_values()`, reusing the existing sparkline machinery
  against the layer's own `_majority` field instead of a
  `study_area_grid` column (these products are per zone, not per cell).
  The study area outline is deliberately not overlaid on these pages: the
  zone polygons already tile the whole study area, and the aggregation
  boundary can sit in a different CRS than the analysis grid - `make_map()`
  combines layer extents without reprojecting, which silently collapses
  the map to a near-empty page when the two CRSes differ. Each
  subnational map's outline is also drawn much thinner than the style's
  normal 0.26mm (`AnalysisReport._thin_vector_outlines()`, report
  rendering only - the interactive map's own style is untouched): at
  that width, hundreds of zones packed onto one page were obscuring
  their own fill colour.
- A second legend page explains the 15-class "by population" bivariate
  scale (5 enablement classes x 3 population tercile classes) as a
  colour matrix, inserted before any map that uses it - a different
  scheme entirely from the plain 0-5 scale the first legend page covers.
  New `AnalysisReport.make_by_population_legend_page()`.
- A new closing "Study Area" page summarises the analysis grid: admin0
  name, analysis scale, cell count, cell size, total analysis area, and
  CRS, read directly from `study_area_grid` and `model.json`. New
  `AnalysisReport.make_study_area_summary_page()`/`_study_area_stats()`.
- The Processing Times page now shows a highlighted "Total analysis time"
  block below the per-indicator chart - the wall-clock span from the
  earliest to the latest recorded timestamp across every
  dimension/factor/indicator, not a sum of each step's own duration,
  which would overstate the real elapsed time for anything that ran
  concurrently - styled like the legend page's "How the scores are
  calculated" note. New
  `AnalysisReport._total_analysis_duration_minutes()`/
  `_draw_total_duration_block()`; `create_execution_time_layout()` now
  returns the Y position it finished at so the block can be placed
  without overlapping a variable-length chart.
- Four new "Insights" pages, inserted after the dimension/factor/
  subnational pages, surface patterns in the analysis grid beyond the
  final score - all computed directly from `study_area_grid`/
  `model.json`, no new geoprocessing:
  - **Factor Score Patterns**: every factor's own score distribution
    (reuses the existing sparkline machinery, just without the map), so
    a spread or heavy low tail hiding inside one factor is visible even
    when the blended score looks fine.
  - **Where Low Scores Come From**: which dimension most often has the
    lowest value among cells scoring 2 or below (the single biggest
    lever for moving the most low-scoring cells up a class), and the
    enablement-class breakdown of cells flagged as an economic
    opportunity (opportunity cells that also score low are the
    highest-priority investment targets).
  - **Settlement and Hazard Patterns**: average score across the whole
    study area vs within GHSL-identified settlements only (how much of
    an apparently "good" score comes from uninhabited land), and average
    score by environmental hazard exposure tercile (does hazard exposure
    correlate with lower enablement).
  - **Factor Correlations**: a diverging-colour heatmap of every
    factor-pair's Pearson correlation - computed PAIRWISE (only
    requiring the two factors in a given pair to both be valid for a
    cell), not across every factor simultaneously, since factors cover
    very different shares of the study area and requiring all of them
    valid at once could leave zero usable cells even with plenty of
    pairwise overlap; pairs below a minimum cell-overlap threshold are
    left blank rather than showing a correlation computed from a
    handful of coincidentally-aligned cells.
  New `AnalysisReport._limiting_dimension_counts()`/
  `_ghsl_settlement_gap_stats()`/`_opportunities_mask_score_histogram()`/
  `_factor_correlation_matrix()`/`_hazard_exposure_tercile_scores()`/
  `_read_grid_columns()`/`_read_grid_columns_with_gaps()`, plus the
  matching page/chart builders and `create_insights_pages()`.
- `SubnationalAggregationProcessingTask` now also computes, for every
  subnational zone, the AVERAGE of every used dimension/factor/the
  overall GeoE3 total across the `study_area_grid` cells that fall
  within that zone - not the majority-class raster statistic the
  existing 4 products use (appropriate for a map legend's discrete
  classes, not for a continuous per-zone score). Computed by spatially
  matching every grid cell to the zone(s) it intersects (a cell
  routinely intersects more than one zone against fine administrative
  boundaries, regardless of the grid's configured cell size -
  confirmed against real data: ~22% of cell/zone matches were shared),
  then a single grouped SQL AVG()
  per zone - not one zonal-statistics raster pass per factor/dimension.
  Idempotent and legacy-safe: only backfills `avg_<column>` columns not
  already present in `geoe3_score_subnational_aggregation.gpkg`, so a
  project whose aggregates predate this feature gets them added on the
  next full analysis run without redoing the existing 4 products. Also
  retains a best-guess zone name field (the aggregation boundary's
  first String-type field - there's no explicit "pick the name column"
  step for it, unlike the admin0 dissolve field) as a new `zone_name`
  column; previously every original attribute except an internal `fid`
  was dropped before computing the existing products. New
  `aggregate_factor_dimension_totals()`/`_detect_name_field()`/
  `_factor_dimension_total_columns()`/`_assign_grid_cells_to_zones()`/
  `_average_grid_columns_per_zone()`/`_write_zone_results()`/
  `_existing_sqlite_columns()`.
- The analysis report's new closing section shows this as a
  "Subnational Score Matrix": one row per administrative zone, one
  colour-coded cell per used dimension/factor/the overall total
  (numbered columns, explained in a key at the end), paginated across
  as many pages as the boundary has zones - there is no cap. Each
  page is rendered as a single raster image rather than one layout
  item per cell: a few thousand individual `QgsLayoutItem`s (routine
  for a fine-grained boundary) brought QGIS's layout engine to a
  crawl in testing against a real 2084-zone boundary; one embedded
  picture per page does not. New
  `AnalysisReport.make_subnational_score_matrix_pages()`/
  `_subnational_score_matrix_columns()`/`_subnational_score_matrix_rows()`/
  `_score_class_color()`/`_render_score_matrix_page_image()`.
- A new "Methodology" section near the end of the report explains, in
  plain language for a non-GIS reader, how each indicator's score was
  actually worked out. The 18 `analysis_mode` values an indicator can be
  configured with mechanically reduce to 7 real-world techniques (e.g.
  counting features in a cell, tracing road-network travel time,
  reading a ready-made hazard map) - the report shows one page per
  technique ACTUALLY used in this project (never the full list of 7
  regardless of relevance), each with a small SVG illustration, a
  descriptive explanation, and the list of this project's own indicators
  that use it, with a one-sentence nuance where a mode differs from its
  technique siblings (e.g. Ookla/GHSL-masked index scores, ACLED's
  per-event-type buffers). A following "Scoring Weights" page lists
  every used dimension's share of the overall analysis and every used
  factor's share of its own dimension, read straight from `model.json` -
  a factor contributing zero weight (e.g. a fallback-only factor) is
  deliberately shown rather than hidden, since the point is transparency
  about what was actually used, not a tidier-looking list. New
  `geest/core/reports/methodology.py` reference module (technique
  registry, `analysis_mode` -> technique mapping, nuance notes) and 7
  versioned SVG illustrations under `geest/resources/methodology/`; new
  `AnalysisReport._methodology_entries()`/`make_methodology_pages()`/
  `_dimension_factor_weightings()`/`make_scoring_weights_page()`/
  `_place_picture()` (a small picture-embedding primitive extracted
  into its own method so tests can mock it instead of constructing a
  real `QgsLayoutItemPicture`).
- **National-scale Active Transport now scores a cell with a score-
  weighted average across every intersecting road/cycle path instead
  of "highest score wins"** (worldbank/GeoE3#397): regional and local
  scale were unaffected by the issue and remain completely unchanged.
  Each feature's own score doubles as its weight
  (`cell_score = sum(score^2) / sum(score)`), so a cell dominated by
  good infrastructure still scores close to the top, a single
  excellent route no longer carries a cell that's otherwise poor, and
  a cell with only poor infrastructure stays low even if one short,
  better-rated segment clips its edge. New
  `select_grid_cells_and_assign_weighted_transport_score()` in
  `geest/core/algorithms/features_per_cell_processor.py` and
  `OsmTransportPolylineWeightedPerCellWorkflow`, dispatched instead of
  the existing max-based workflow only when `analysis_scale ==
  "national"`. Described in both the analysis report's Methodology
  section and the live item info panel's methodology slide-over via a
  new "A Score Weighted Toward the Best Infrastructure" technique and
  a scale-aware `technique_for_indicator()` (the technique lookup was
  previously a pure function of `analysis_mode` alone, which can't
  tell national/regional/local Active Transport apart since they share
  the same `analysis_mode` string); new
  `geest/resources/methodology/weighted_feature_average.svg`.

### Fixed

- **The toolbar button's tooltip read "GeoE3 Settings"**, which doesn't
  describe what it does. It toggles the GeoE3 dock panel's visibility,
  already reflected correctly after the first click ("Show GeoE3
  Panel" / "Hide GeoE3 Panel"). The panel is visible by default on
  load, so the initial tooltip now reads "Hide GeoE3 Panel" to match.
- **Settings toggled in Settings > GeoE3 (e.g. "Include Subnational
  Score Matrix") could silently revert after restarting QGIS**, even
  when correctly unchecked and confirmed with OK every time.
  `set_general_setting()` wrote the new value into a QSettings object
  but never called `sync()`, relying instead on that object's
  destructor - triggered by Python garbage collection, not guaranteed
  to run before QGIS's own shutdown sequence tears down the interpreter
  - to actually flush the write to disk. Every setting the plugin
  stores was equally at risk; this one was just the most noticeable
  since it's toggled against its own default. Now syncs explicitly on
  every write and delete.
- **"Include Subnational Score Matrix" (and in principle any other
  boolean setting in Settings > GeoE3) could still show checked
  immediately after being unchecked and saved**, even with the sync
  fix above in place - a second, separate bug on the read side.
  `QSettings.value()`'s implicit Python-type coercion when no explicit
  `type=` is given turned out to be binding/platform-dependent: on a
  real QGIS 4 install it returned the literal ini string `"false"`
  rather than a native bool, and `bool("false")` is `True` in Python
  (any non-empty string is truthy), so every `bool(setting(...))` call
  site read a freshly-saved "off" value straight back as "on".
  `general_setting()` now infers the expected type from the caller's
  own `default` (bool/int/float/str) when `expected_type` isn't given
  explicitly, so `QSettings` does the conversion itself instead of
  leaving it to chance - fixes every setting read this way, not just
  this one checkbox.
- The item info panel's progress page (status text + the two progress
  bars, shown while a run is active) didn't survive collapsing and
  re-expanding the panel mid-run, or selecting a different tree item -
  either silently dropped back to "Selected item" even though the run
  was still going. `set_expanded(True)` now re-forces the progress page
  whenever a run is active, and `show_item()`/`clear()` (triggered by
  tree selection changes) no longer switch the stack away from it while
  one is - both still update their own content underneath, ready for
  when the run actually finishes and `hide_progress()` is called.
- **"Clear Item" on the Analysis tree node was noticeably slower than on
  any other role.** Its own outputs span 5 separate `study_area_grid`
  columns (`geoe3`, `geoe3_by_population`, `geoe3_masked`,
  `geoe3_by_population_masked`, `opportunities_mask`), and clearing them
  one at a time paid a full GeoPackage open/transaction/WAL-TRUNCATE-
  checkpoint round trip 5 times in a row, serialized under a process-wide
  write lock - every other role only ever touches one column. New
  `geest.core.grid_column_utils.clear_grid_columns()` clears several
  columns in a single pass instead; `TreePanel._clear_single_item_outputs()`
  uses it for the Analysis role. `clear_grid_column()` (singular) is
  unchanged for its other ~10 existing single-column callers.
- Tightened the wording of roughly twenty report headings/subtitles/body
  paragraphs across the legend, by-population, analysis overview,
  subnational, insights, subnational score matrix, methodology and
  scoring weights pages - reviewed string by string against the live
  report and rewritten for plainer, less repetitive phrasing. No
  behaviour change.
- **Subnational Score Matrix row/column labels were too small to read.**
  `_render_score_matrix_page_image()`'s font bumped from 5.5pt to
  15pt in two steps (row height 5mm->12mm, header height 7mm->16mm
  to match), and the "Subnational Score Matrix — Key" page now comes
  BEFORE the table pages instead of after them, so the column numbers
  are already known by the time a reader reaches the first table page.
- The Subnational Score Matrix is now OFF by default - a new "Include
  Subnational Score Matrix in the analysis report" checkbox under
  Settings > GeoE3 > Analysis Options opts back in. It can add a very
  large number of pages for a project with many administrative zones,
  so it shouldn't appear unasked-for in every report. New
  `include_subnational_score_matrix` setting (default `False`) and
  `AnalysisReport._subnational_score_matrix_enabled()`.
  `SubnationalAggregationProcessingTask.run()` now also checks the same
  setting before computing the underlying `avg_<column>` zone averages
  at all - no point paying for the spatial join plus a SQL `AVG()` pass
  per zone when the setting is off and no report will ever read them.
- **The running-item spinner now animates in place of the status icon
  (column 1) instead of inserting a separate widget there.** Inserting/
  removing a widget via `treeView.setIndexWidget()` every time a
  workflow started or finished was a source of unwanted tree-panel
  resizing. `JsonTreeItem.getStatusIcon()` now shows the current
  animation frame (`set_spinner_pixmap()`/`clear_spinner_pixmap()`)
  while a workflow runs, refreshed via `dataChanged` on that one cell -
  the same self-sizing column, no widget insertion. As a side effect,
  the spinner's size is no longer derived from `QTreeView.rowHeight()`,
  removing the whole class of "invalid/unresolvable row height"
  corruption this relied on working around.
- **"GHSL Settlements" reported "Layer added to map" but nothing ever
  rendered.** Unlike `add_to_map()`/`add_grid_layer_to_map()`,
  `add_ghsl_settlements_to_map()` never re-enabled visibility on the
  layer or its parent groups after adding it - if "GeoE3 Study Area"
  (or an ancestor) was ever unchecked for any reason, the layer stayed
  invisible with no self-healing re-check, even though it loaded
  successfully.
- **"Clear Item" on the Analysis node silently deleted nothing.**
  `item.getPaths()` only knows how to build a path for
  indicator/factor/dimension hierarchies and returns `[]` for the
  analysis item itself, so `_clear_single_item_outputs()` resolved its
  output directory down to the whole project folder instead of
  anywhere any of its outputs actually live. A later "Run Item
  Workflow" then found stale per-area rasters from an earlier run
  still on disk and skipped reprocessing those areas as "already
  done", silently leaving an inconsistent mix of stale and freshly
  regenerated areas with no error ever raised. Clearing the analysis
  item now clears all six of its real output directories
  (`geoe3_score`, `geoe3_by_population_score`,
  `geoe3_score_ghsl_masked`, `geoe3_score_by_population_ghsl_masked`,
  `opportunity_masks`, `subnational_aggregation`) and all five of its
  own `study_area_grid` columns. `item.gridColumnName()` had the same
  gap - the analysis item has no `id` attribute, so it fell through to
  `""` and reached `clear_grid_column()` with a blank name, failing
  with a SQLite "no such column" error; `clear_grid_column()` now also
  refuses a blank column name outright as defense in depth.
- **"GeoE3 x Opportunities Mask" (and its by-population variant) always
  showed blank in the tree and report, even on a fully successful run.**
  `OpportunitiesByWeeScoreProcessingTask`/`...PopulationProcessingTask`
  correctly compute the masked score and write
  `geoe3_score_ghsl_masked_result(_file)` /
  `geoe3_score_by_population_ghsl_masked_result(_file)` onto the analysis
  item, but `JsonTreeModel.loadJsonData()` rebuilds that item's attributes
  from an explicit, hardcoded whitelist whenever the model is reloaded
  from saved JSON - these two keys were missing from it, so the result
  was silently dropped on the next reload despite the underlying raster
  being computed correctly. Added them to the whitelist, and removed two
  report rows ("Score × opportunities", "Population × opportunities")
  that read an older, superseded key name no processor has written in a
  long time - they duplicated the already-correct "GHSL masked" rows.
- **Scoring a study area's grid against network-analysis isochrones could
  take over an hour for a single, densely-populated area,** versus seconds
  for a sparser one. `write_buffer_values_to_grid()` tested every grid cell
  against every distance band with a plain, unprepared
  `QgsGeometry.intersects()` call - fine for a handful of tests, but a
  dissolved isochrone band from thousands of points can carry hundreds of
  thousands of vertices, and the same few band polygons get tested against
  every one of potentially hundreds of thousands of grid cells. Each band
  now gets a prepared `QgsGeometryEngine` (built once, reused for every
  cell), and for `MAX` aggregation - the only mode any caller actually
  uses - bands are tested score-descending with matched cells dropped from
  consideration, so a cell already at its best possible score is never
  tested against a lower-scoring band again.
- **`scripts/start_qgis.sh`/`start_qgis_ltr.sh` logged to `~/GEOE3.log`,**
  away from wherever validation tests are actually run from. Logs now
  write to `GEOE3.log` in the project folder instead, so they can be
  tailed from the same place (`tail -f GEOE3.log`).
- **Multi-buffer network analysis clipped the road network to the whole
  study-area polygon instead of the points actually being analysed,**
  wasting graph-build and traversal time on network nowhere near any
  point whenever points were sparse relative to the area (the common
  case). `_clip_network_to_area()` now clips to a dissolved buffer around
  the points themselves - the isochrone computation only ever needed
  network within `max(distances)` of an actual point, so this changes
  nothing about the result, only how much irrelevant network gets
  clipped and traversed to produce it.
- **The animated throbber on a running tree item could silently freeze on
  its last frame while the item was still computing.** `self.child_movie`/
  `self.parent_movie` were a single shared pair of attributes rather than
  tracked per item - with two items' start/stop events overlapping
  (`concurrent_tasks` > 1, or just two sequential items racing),
  `_stop_item_spinner()` could stop a *different*, still-running item's
  movie instead of the one that actually finished. Spinners are now
  tracked per item (keyed by guid), so starting/stopping one item's
  animation can never affect another's.
- **No spinner ever showed at all for a single-indicator factor** (e.g.
  "Access to Public Transport", where its one indicator is promoted to
  display in the hidden factor's place). `JsonTreeModel._findIndexByGuid()`
  can locate a hidden item's own *children* but never the hidden item
  itself, so looking up the hidden parent's own index always failed.
  `on_workflow_started()` then unconditionally used that invalid index's
  `rowHeight()` (a degenerate 0/-1) to scale the *child's own* spinner,
  silently shrinking it to an invisible size even though it was genuinely
  running. The lookup is now guarded so an unresolvable parent leaves the
  child's own (already-correct) row height untouched.
- **The tree panel kept resizing during analysis execution.** Its status
  label (e.g. "Processing area 16/16") sat at a fixed 200px width inside
  the same row as the two fixed-200px progress bars and several buttons
  that hide/show as a run starts and stops - the row's required minimum
  width jumped between "idle" and "running" states as those widgets
  toggled visibility. The status label now has its own row, spanning the
  full panel width, directly above the progress-bar row.
- **Re-running or clearing a single indicator left its factor, dimension, and
  analysis still showing a stale "Completed successfully" with the old
  aggregate value.** Nothing ever told an ancestor its cached aggregate was
  computed from a now-changed child. `JsonTreeItem.invalidateAncestors()`
  clears every ancestor's `result`/`result_file` on a successful workflow
  run and when an item is cleared via "Clear Item", so the tree honestly
  falls back to "Configured, not run" until the aggregate is recomputed.
- **`study_area_grid` could silently gain a permanent, unnamed, all-NULL
  column.** An item with an empty/missing `id` attribute reached the grid
  column creation code with a blank column name. `_ensure_column_exists()`
  and `add_model_columns_to_grid()` now refuse to create a blank-named
  column.
- **Three dead aggregate columns (`contextual_score`, `accessibility_score`,
  `place_characterization_score`) were added to every study area's grid.**
  Confirmed via git history that these were reserved alongside
  `wee_score`/`wee_by_population` (since renamed to `geoe3`/
  `geoe3_by_population`) but never implemented - removed from
  `get_aggregate_column_names()`.
- **Logging never reached `~/GEOE3.log`.** A module-level diagnostic
  banner in `grid_column_utils.py` could fire before `geest/__init__.py`'s
  own `logging.basicConfig()` call, implicitly self-configuring the root
  logger first and making our call a silent no-op (console showed the
  bare `WARNING:root:...` fallback format instead). `basicConfig()` now
  passes `force=True` so our file handler always wins.
- **Analysis-level processing required a population raster even though it's
  optional.** Leaving it unset errored with "Select a valid population
  raster before running the analysis" and aborted the whole analysis
  post-processing step. The GeoE3 x Population Score is now skipped
  (like the opportunities mask already was) when no population raster or
  S2S demographics are configured, and everything else still runs.
- **GHSL-filtered (unpopulated) areas were reprocessed on every single run.**
  Study area creation already skips grid generation for an area with no
  GHSL settlements, but `AreaIterator` never checked for that - every
  indicator workflow ran its full per-area pipeline on these areas anyway,
  every run, only to find nothing to write. `AreaIterator` now skips any
  area with zero `study_area_grid` cells up front, determined directly
  from the grid itself so it works immediately on existing projects too.
- **Running multiple indicators concurrently (the "concurrent tasks"
  setting) could silently lose grid writes - an indicator reported
  "Completed" with no error, yet its own `study_area_grid` column stayed
  NULL (or an aggregating factor/dimension read it as 0).** Confirmed
  against a real project: three Contextual-dimension indicators started
  within 6ms of each other (genuinely concurrent, not sequential), and only
  one of the three actually persisted its value. Reproduced reliably with a
  new test (`test_grid_column_concurrent_writes.py`) that fires several
  threads at the same GeoPackage the way concurrent indicator workflows do
  - each opens its own independent `ogr.Open(gpkg_path, 1)` connection and
  writes a different column with a raw SQL `UPDATE`; under true
  concurrency, most of those writes failed outright even though each one's
  own `StartTransaction()`/`CommitTransaction()` reported success -
  SQLite's own locking does not fully protect independent GDAL/OGR dataset
  handles writing to the same file from different threads in the same
  process. Fixed by funnelling every `study_area_grid` write (11 functions
  in `grid_column_utils.py`: the uniform-value writer index-score
  indicators use, the aggregation writer factors/dimensions use, spatial
  joins, buffers, percentage scores, etc.) through one process-wide lock
  (`@_serialize_grid_writes`) - only the actual database write is
  serialized; the slow, genuinely parallelizable work (loading features,
  generating rasters) is unaffected.
- **Windows crash running a whole dimension (#447, #448):** every indicator's
  workflow opened its own `AreaIterator` (three fresh `QgsVectorLayer` reads)
  against `study_area.gpkg` while `grid_column_utils` concurrently wrote to
  the same file - safe in isolation, but running many indicators back-to-back
  (a whole dimension/factor/analysis) raised the odds of hitting a GDAL/OGR
  SQLite handle corruption window, surfacing on Windows as an access
  violation inside `getFeatures()`. The SQLite write-safety hardening (WAL
  journal + `SQLITE_USE_OGR_VFS=NO`) that already fixed this exact class of
  corruption for study-area *creation* was explicitly scoped out of the later
  analysis/workflow *execution* phase - closed that gap by applying the same
  hardening around `WorkflowQueueManager`'s run lifecycle (extracted into a
  shared `geest.utilities` helper so both call sites share one
  implementation).
- **One bad area no longer aborts the whole indicator.** `WorkflowBase`'s
  per-area loop wrapped all ~27 areas in a single `try/except`, so any
  unhandled exception from one area (a degenerate geometry, a transient
  data-source hiccup, ...) discarded every area already processed and
  skipped every area still to come - the "hard to reproduce, whole run just
  fails" shape of several field reports. Each area is now isolated in its
  own `try/except`: a failure is logged clearly against that specific area
  and the run continues; the final result records which areas (if any) were
  skipped. If literally every area fails, that's still reported as a real
  failure, not a false "Completed". Also: a user-cancelled run previously
  kept processing all remaining areas regardless (the cancellation flag was
  checked but never acted on) - it now stops promptly.
- **Local-scale (100m grid) analysis could take 7.5+ hours and still not
  finish, versus 7 minutes at national (1000m) scale on the same country
  (#445) - roughly 100x more grid cells causing a much-worse-than-linear
  slowdown.** Root cause: `write_spatial_join_to_grid` (environmental
  hazards, GHSL/Ookla masking, vector-fallback nighttime lights) re-queried
  the features layer with `SetSpatialFilter` for *every* grid cell instead
  of indexing once; `write_percentage_scores_to_grid` (multi-buffer
  accessibility scoring, the WTP dimension from #448) ran a full exact GEOS
  intersection against the dissolved buffer polygon for *every* grid cell
  with no cheap bounding-box reject first. Both now build/check a spatial
  index once and do indexed lookups per cell, matching the pattern
  `write_buffer_values_to_grid` already used correctly. Also found and fixed
  the same anti-pattern in dead code (`write_point_count_to_grid`, unused -
  removed rather than fixed, per YAGNI).
- `multi_buffer_distances_native_workflow.py` (the WTP/accessibility
  workflow) reopened the road network file and re-ran a full-layer CRS
  reprojection from scratch for every area (up to 27x per indicator, times
  every indicator in the dimension), even though the network and its CRS
  don't change between areas. Now loaded and reprojected once and cached.
- Five workflows (`polyline_per_cell`, `polygon_per_cell`,
  `osm_transport_polyline_per_cell`, `classified_polygon`, `safety_polygon`)
  loaded their input layer without checking `.isValid()`, unlike every other
  per-cell workflow - a corrupt or no-longer-reachable source file didn't
  fail loudly; it surfaced as "0 features in every area", silently absorbed
  by the empty-features fallback into an all-zero result with nothing
  pointing at the real cause. Now raises a clear `WorkflowNotConfiguredError`
  naming the broken path, matching the existing `point_per_cell` pattern.
- The S2S Education-proxy grid update (`polygon_per_cell_workflow.py`) used
  a raw `ogr.Open`/`ExecuteSQL` call with no retry on a transient "database
  is locked" error, unlike every other grid-writing function in this
  codebase. Now goes through the same `_open_gpkg_for_write`/
  `_execute_sql_with_retry` helpers as everything else.
- OSM point and mixed-to-point downloads (health facilities, schools,
  pharmacies, financial services, kindergartens, grocery stores, green
  spaces, public transport, water points) now retain the OSM `name` tag
  as an entity name attribute, instead of only the feature `id`. Polygon
  downloads gain the same `name` attribute (#453).
- S2S download is no longer offered for flood hazards at local or
  national analysis scale. Flood now follows the same regional-only S2S
  gating as every other environmental hazard (#449).
- A broken/missing road network layer reference could linger silently in
  `model.json` forever: when the Road Network panel detected the file was
  gone it tried to clear the stored path, but the clear signal's value was
  discarded by the receiving slot (which re-fetched the combo box selection
  instead) and the slot also silently ignored empty/`None` values, so the
  stale path was never actually removed. Setting the road network layer now
  validates the file exists before storing it (showing a clear error if
  not), clearing is no longer a no-op, and a missing file detected on
  restore now also surfaces a message-bar warning instead of only a log
  line.
- Contextual index-score indicators (e.g. workplace discrimination) could
  fail with "VRT Layer generation failed" when a study area contained a
  sliver/island fragment too small to have been assigned any
  `study_area_grid` cells. `rasterize_grid_column` silently fell back to
  rasterizing the whole study area's extent for such an area (burning
  nothing, since no grid rows matched), producing a degenerate raster that
  broke downstream masking and VRT combination - either aborting the whole
  indicator or corrupting its combined output depending on exact pixel
  rounding. `rasterize_grid_column` now detects the zero-matching-cells
  case up front and refuses to rasterize, and
  `ContextualIndexScoreWorkflow` treats that as "no features for this
  area" and falls back to a neutral (zero) raster for just that one area,
  matching the existing fallback behaviour used elsewhere for areas with
  no input features. A single, un-partitioned study area can legitimately
  leave `area_name` NULL on every `study_area_grid` row while still naming
  the area itself - that case is distinguished from a genuinely missing
  sliver (grid cells exist for other areas, just not this one) so it still
  rasterizes normally instead of being skipped.
- Masking a raster to a geometrically thin area (a narrow coastal strip or
  sliver islet, not necessarily a small one) could fail entirely:
  `gdal:cliprasterbymasklayer` with `CROP_TO_CUTLINE` snaps the crop window
  to pixel boundaries, which can round down to zero rows or columns even
  when the source raster is perfectly valid, so `gdalwarp` refused to
  create a 0-sized dataset and no masked file was written. `_mask_raster`
  silently returned that nonexistent path anyway, so the area vanished from
  the combined VRT with no error reported (seen as `entrepreneurship_index`
  dropping several Cabo Verde islands while still reporting success).
  `_mask_raster` now detects a failed/degenerate crop and retries without
  `CROP_TO_CUTLINE`, keeping the source raster's own (already-valid) extent
  and masking only the pixel values - and raises clearly if that still
  doesn't produce a valid raster, instead of returning a bogus path.
- `factor_aggregation` and `dimension_aggregation` (the workflows behind
  every factor/dimension/analysis rollup, e.g. workplace discrimination's
  factor score) aborted the *entire* indicator with "produced no raster
  output for area cv_part20" whenever one area had no matching
  `study_area_grid` cells - the same sliver-area condition fixed above,
  but `AggregationWorkflowBase` lacked the `supports_empty_features_fallback`
  flag that lets a single ungridded area fall back to a neutral raster
  instead of failing the whole run. It now sets that flag like the other
  grid-first workflows, so one gridless sliver no longer blocks the
  factor/dimension/analysis score for the other 26 areas.
- **The `supports_empty_features_fallback` safety net above had a second,
  much more damaging side effect: it could silently wipe an indicator's,
  factor's or dimension's entire `study_area_grid` column back to NULL
  after a real, successful write** - seen as values present in the log
  ("Executing: UPDATE study_area_grid SET workplace_index = 2") and gone
  moments later ("Clearing column: UPDATE study_area_grid SET
  workplace_index = NULL"), with every downstream indicator/factor/
  dimension layer rendering as empty/red. `_apply_grid_column_zero_fallback()`
  fires for *any* area with zero matching grid cells or zero input
  features (not just slivers - an area simply having no OSM points/hazard
  polygons/etc. for this particular indicator is routine), and the first
  time it runs per workflow instance it unconditionally issued
  `UPDATE study_area_grid SET col = NULL` with no `WHERE` clause - every
  row, every area. Nine grid-first workflows each tracked their own
  separate "have I cleared this column yet" flag (`_column_cleared` on
  `PointPerCellWorkflow`/`PolygonPerCellWorkflow`/`PolylinePerCellWorkflow`/
  `SinglePointBufferWorkflow`/`MultiBufferDistancesNativeWorkflow`;
  `_grid_value_written`/`_grid_aggregated` on
  `ContextualIndexScoreWorkflow`/`IndexScoreWorkflow`/
  `AggregationWorkflowBase`) that was never synchronised with the base
  class's own `_grid_column_cleared` flag the fallback actually checks -
  so whichever area first had no features/cells (commonly *after* several
  other areas had already written real data) triggered the fallback's
  clear regardless of whether the column had, in fact, already been fully
  and correctly written. All nine now set `self._grid_column_cleared =
  True` immediately after their own successful write, so the fallback
  correctly limits itself to filling in the one empty area instead of
  wiping every other area's result.
- Every grid-write function in `grid_column_utils.py` now wraps its SQL
  `UPDATE`(s) in an explicit `StartTransaction()`/`CommitTransaction()`
  pair, checking the commit's return code and raising loudly if it fails,
  instead of relying on an unchecked `PRAGMA wal_checkpoint` + dataset
  close to persist the write (`gpkg_doctor.checkpoint_dataset()` swallows
  all exceptions by design, on the assumption that `GDALClose()` would
  still flush on its own - this codebase has already hit cases where that
  assumption doesn't hold, see the Windows GDALClose/access-violation fix
  above). Not the root cause of the data-loss symptom described above,
  but a real gap worth closing defensively.
- **Clearing a single indicator/factor/dimension left its on-disk outputs,
  `study_area_grid` column, and map layer behind.** `clear_item()` only
  reset the item's own status/result attributes - its masked rasters stayed
  on disk, its grid column kept its last value, and its layer stayed in the
  legend. Now also deletes the files directly inside the item's own
  workflow directory (never recursing into child subdirectories, so
  clearing a factor doesn't touch its indicators' outputs or vice versa),
  blanks the item's own grid column (new `JsonTreeItem.gridColumnName()`,
  matching the sanitisation `add_model_columns_to_grid()` used to create
  it), and removes the item's own layer(s) from the legend/registry via a
  new `geest.core.utilities.remove_from_map()` - which leaves the subgroup
  holding the item's children's layers/groups completely untouched.
- **Clearing a single-indicator factor's row cleared the indicator but left
  the factor itself untouched** - found against a real project (Cabo
  Verde): clearing the Contextual dimension correctly blanked
  `dim_contextual`, but each of its three single-indicator factors kept
  their stale "Completed" `fac_*` column/result/rasters after being
  "cleared". Root cause: `JsonTreeModel.data()` hides a factor with exactly
  one child indicator from the tree entirely, promoting that indicator's
  row to display in the factor's place labeled with the factor's name - so
  the one row a user sees and right-clicks ("Workplace Discrimination")
  really represents two tree items (the factor and its indicator) sharing
  a single visible row, and `index.internalPointer()` for that row returns
  the indicator, not the factor. `clear_item()` now also clears the hidden
  parent factor whenever the selected item is an indicator behind one
  (recursion still stops there - a factor with multiple, independently
  selectable children is untouched by clearing one of them, as before).
- **Rasterized output was entirely empty for every single-area (un-
  partitioned) project, even though the underlying `study_area_grid`
  column held the correct values** - found via a new end-to-end test
  driving the real clear/edit/run flow and sampling the actual raster
  pixels, not just checking the result file existed.
  `rasterize_grid_column()` builds a `WHERE area_name = '...'` clause, then
  has fallback logic for projects that never populate `area_name` on their
  grid rows at all (a single, un-partitioned area): it correctly detects
  that case and drops the attribute filter used to compute the raster's
  *extent*, but never dropped the same `where_clause` string handed to the
  actual GDAL burn - which still matched zero rows, so `gdal.Rasterize()`
  wrote nothing but its `nodata` fill value everywhere. The grid column
  (written directly over SQL, unaffected) was always correct; only the
  rasterized/combined-VRT output was empty. Both now derive from the same
  decision.
- **A plain Run (no Shift) on a dimension/factor silently kept using an
  indicator's OLD index score after it was edited**, when that indicator
  is hidden behind its single-child factor row and so can never be cleared
  directly from the tree: `queue_workflow_task()`'s "skip if already
  complete" check only looks at the item's own `result_file`, which
  editing `index_score` alone never touched. Fixed in
  `FixedValueDataSourceWidget.update_attributes()` - changing the value now
  blanks the indicator's own `result`/`result_file`, so the normal
  skip-if-already-complete check correctly recognises it needs to run
  again, without the user needing to know to hold Shift.
- **Writing the per-zone dimension/factor/total averages
  (`SubnationalAggregationProcessingTask._write_zone_results()`) failed on a
  real Nix-based QGIS install** with "mod_spatialite.so: cannot open shared
  object file", even though it worked fine against the qgis/qgis Docker
  image this was first verified against: a bare `sqlite3` connection needs
  `mod_spatialite` loaded by name to satisfy the aggregates GeoPackage's own
  RTree-trigger `WHEN` clauses, and Nix has no standard library search path
  for a bare `.so` name to resolve against (hard-coding a nix store path
  would be unique to the machine that built it). Now writes through
  GDAL/OGR's `ExecuteSQL()` instead (`grid_column_utils.py`'s
  `_open_gpkg_for_write()`/`_execute_sql_with_retry()`/`_commit_or_raise()`),
  which already has those functions built in - the same reason every other
  GeoPackage write in this codebase goes through OGR rather than a bare
  `sqlite3` connection.

### Changed

- Grid-first workflows (`ContextualIndexScoreWorkflow`, `AggregationWorkflowBase`
  - index scores, factor/dimension/analysis aggregation) wrote their value
  to `study_area_grid` with one whole-table SQL `UPDATE` per area, even
  though that SQL has no area filter and produces an identical result every
  time - for a 27-area study area that meant running the same multi-second
  `UPDATE` 27 times over. It now runs once per workflow; per-area
  rasterizing, masking, and VRT-combining (needed to keep the output raster
  sparse rather than one dense bounding-box raster) are unchanged.

### Fixed

- **Road network layer selection was silently lost or leaked across
  projects.** Three related bugs, all traced from the same root cause -
  the Road Network panel's `QgsMapLayerComboBox` lived for the whole
  session and reacted to *any* change in QGIS's layer registry, not just
  the user explicitly picking something:
  - Picking a layer before a GeoE3 project was open wrote it onto the
    in-memory default template (not the real project), then only logged
    a warning that the save was skipped - the pick vanished the moment a
    real project loaded. `TreePanel.set_road_network_layer_path()` now
    refuses the write outright and shows a visible warning instead.
  - Opening a different GeoE3 project while the previous one's layers
    were still trickling out of the registry let the combo auto-select
    one of them and write it into whichever project's `model.json`
    happened to still be "current" at that instant - corrupting one
    project's road network reference with another's layer (observed
    live: a reprojected copy of one country's cycle-path layer ending up
    as another's road network, silently zeroing out its Active
    Transport/multi-buffer-point indicators).
  - `RoadNetworkPanel.reproject_selected_layer()`'s in-memory
    `_reprojected_layers` cache could outlive the QGIS layer it wrapped,
    crashing with `RuntimeError: wrapped C/C++ object of type
    QgsVectorLayer has been deleted` the next time it was consulted.

  Root-caused to the always-live combo itself, so it's been replaced:
  `RoadNetworkPanel` now shows a read-only label fed from `model.json`,
  with a "Load / Change Network Layer" row (inline combo + browse + Ok/
  Cancel, no popup) that only writes on an explicit Ok -
  `_finalize_road_layer_selection()` is the only place
  `road_network_layer_path_changed` is ever emitted from. The
  `_reprojected_layers` cache is gone; reprojection reuse is now a
  deterministic disk-path check scoped to the current project's own
  `study_area/` folder instead of a QGIS-session-wide registry scan.
- `GeoE3Dock`'s three `restore_layer_from_path()` call sites were gated
  behind `if saved_path:`, so a project whose stored road network path
  was genuinely empty never got that reflected in the panel - it kept
  showing whatever the previously-viewed project's layer was. The guard
  is removed; an empty path is now a real state the label displays.

### Changed

- Road Network panel layout: status badge, path label, and the
  "Load / Change Network Layer" button (and its inline combo/Ok/Cancel
  replacements) are centered and full-width, matching the OSM download
  button. Dropped the redundant "Select a road network layer for the
  study area." instruction label.

## [2.0.6] - 2026-10-13

### Added

- Reverse-engineered Software Requirements Specification under `srs/`
  (branded Word + PDF deliverables, 18 UML diagrams as SVG, one-shot
  `srs/build.sh` pipeline writing directly into the Kartoza Word template).
- SRS build toolchain in the dev shell (plantuml, python-docx, pillow,
  libreoffice, Lato).
- GeoPackage corruption causal analysis
  (`docs/gpkg-corruption-causal-analysis.md`).
- SRS chapter 8 "Shipped model catalogue", generated from
  `geest/resources/model.json` at build time
  (`srs/scripts/gen_model_catalogue.py`): a page per dimension and per
  factor, every indicator with its defaults, brand-styled WBS tree diagrams
  per dimension, and an indicator × processor capability matrix rendered as
  SVG/PNG.
- QGIS launcher scripts now symlink the working-tree plugin into the GEOE3
  profile's `python/plugins` folder before launching
  (`scripts/ensure_plugin_link.sh`).
- Launcher scripts pin QGIS to a light palette even when the desktop is in
  dark mode (`scripts/qgis_light_theme_startup.py` via `PYQGIS_STARTUP`;
  Qt 6.8+ colour-scheme override with a light-Fusion-palette fallback).
- GeoPackage write-path hardening (causal analysis §5, all four items):
  chunk tiles now go through the single unified writer connection, every
  WAL checkpoint in the process is serialised behind one lock, all layers
  (including `chunks`) are pre-created before worker threads start, and
  map refreshes are deferred while the writer is active.
- `admin.py generate-zip` now runs pre-flight checks before packaging:
  aborts if the version in `config.json` is already published on
  plugins.qgis.org, or if the checked-in `geest/metadata.txt` has drifted
  from `config.json` (`--skip-checks` to bypass for local iteration).
- Categorised `nix develop` command reference covering the full plugin
  lifecycle (`scripts/dev-help.sh`), replacing the old ad-hoc banner text.

### Changed

- The analysis report has been completely redesigned: a flat, World Bank-
  appropriate visual language (navy/cyan bands, hairline footers, page
  numbers), a proper horizontal bar chart for processing times, clean map
  neatlines with outside-frame coordinate annotations, and minimap grids —
  the overview page shows the overall score plus dimension minimaps, each
  dimension page its factor minimaps, and each factor page its indicator
  minimaps. Funding/attribution moved to a styled closing page, blank pages
  are impossible (layer validity is checked first), the cover typo is fixed,
  and report maps no longer depend on the project CRS (which also hung
  report generation when no project CRS was set). `export_pdf` gained an
  optional dpi override for fast draft exports.
- The flake now sources QGIS from nixpkgs: `qgis` 4.x (latest) and
  `qgis-ltr` 3.44.x; the geospatial-nix and qgis-source inputs were removed
  and `flake.lock` updated accordingly. nixpkgs is pinned to the last
  revision with binary-cached QGIS builds.
- Dev shell Qt tooling moved from Qt 5 to Qt 6 (`kdePackages.*`) to match
  QGIS 4.x — nixpkgs rejects mixed Qt shells; each QGIS variant now gets the
  matching PyQt WebEngine binding (PyQt6 for 4.x, PyQt5 for LTR).
- The dev shell recreates `.venv` automatically when the nix python
  interpreter changes (a stale venv made pip write into the read-only
  store).
- All pre-commit hook tooling (`black`, `flake8` + `flake8-docstrings` +
  `pydocstyle`, `isort`, and the `pre-commit-hooks` basics) is now
  provisioned by the nix flake instead of pre-commit fetching its own
  copies from PyPI/GitHub on every machine; the dev shell reinstalls the
  git hook on every `nix develop` so a nixpkgs pin bump can no longer leave
  a hook with a dangling store-path shebang.

### Fixed

- GeoE3 by population yields no result in national-scale analyses (#455).
- A disabled factor no longer re-enables itself unexpectedly (#450).
- The indicator description window now updates dynamically when switching
  indicators (#446).
- A broken or missing data source on one indicator no longer aborts a
  multi-indicator run with a raw Python traceback: workflow start-up
  errors are trapped at the queue boundary, the indicator's status icon
  flips to failed with an accessible explanation in its tooltip, and the
  rest of the queue continues. The known config-validation raises
  (multi-buffer, point-per-cell, OSM transport) now produce plain-language
  messages.
- GHSL tile download failures now raise a descriptive `GhslDownloadError`
  instead of surfacing later as a bare `FileNotFoundError` from zipfile;
  corrupt cached zips are removed so the next attempt re-downloads. The
  GHSL integration tests skip (rather than error) when the JRC service is
  unreachable, so CI no longer fails on network flakiness.
- SRS PDF conversion silently substituted DejaVu for the brand fonts and
  dropped bold: `srs/build.sh` now provisions Lato and JetBrains Mono via a
  throwaway fontconfig so PlantUML and LibreOffice embed the correct faces.
- GeoPackage self-healing hardening: locked/busy check results are now
  classified as "could not assess" instead of corruption, so the healer can
  never rebuild-and-swap a healthy database that is merely held by an active
  writer (regression tests added).
- QGIS 4 / PyQt6 crash in the open-project panel: `event.Resize` instance
  enum access replaced with `QEvent.Type.Resize` (works on PyQt5 too).
- QGIS 4 / PyQt6 plugin-load failures: all remaining unscoped Qt enum
  accesses (`QTreeView.InternalMove`/`NoEditTriggers`,
  `QFileDialog.ExistingFile`/`AcceptSave`, `QDockWidget.DockWidget*`,
  `QScrollArea.NoFrame`, `QAbstractScrollArea.AdjustToContents`,
  `QAbstractSpinBox.UpDownArrows`) replaced with their scoped forms — every
  Qt attribute reference in the package is now mechanically verified against
  both PyQt5 and PyQt6 by a new regression test
  (`test/test_qt_enum_compliance.py`), so this bug class is caught by the
  suite instead of at plugin load.
- QGIS 4 / PyQt6 crash when resizing data-source widgets: three widgets
  read `PM_DefaultFrameWidth` off a style *instance* — replaced with
  `QStyle.PixelMetric.PM_DefaultFrameWidth`, and the enum compliance test
  now also bans instance enum-member access (`style().PM_*`, `event.X`).
- Active Transport skipped as "unconfigured" although a layer was set: the
  polyline workflow now accepts the layer under any of its sibling mode
  keys (`osm_transport_polyline_per_cell_*`, `road_network_layer_path`),
  so switching analysis mode no longer orphans a configured layer; the
  decline log lists exactly which data-source keys are present. A new
  end-to-end suite (`test/test_workflow_job_e2e.py`) runs a real indicator
  through the production queue → job → factory → workflow chain on both
  QGIS images, covering the run path unit tests missed.
- Crash when running an indicator with no data source configured: six
  workflow `__init__` methods did `return False` on missing/invalid
  sources, which Python rejects with `TypeError: __init__() should return
  None`. They now raise `WorkflowNotConfiguredError`; the queue manager
  skips the job with a log entry and the tree panel shows a message-bar
  hint naming the unconfigured indicator. An AST regression test
  (`test/test_workflow_init_hygiene.py`) bans value-returns in workflow
  `__init__` methods.
- Plugin reloads no longer stack duplicate dock widgets: `unload()`
  reparents the dock before the queued deletion, and `initGui()` sweeps
  stale `GeoE3DockWidget` instances left by a crashed previous load.
- Plugin reloads no longer stack duplicate toolbar buttons ("GeoE3
  Settings" et al.): every unload phase is individually guarded so one
  failing step cannot abort the cleanup, all toolbar actions carry
  objectNames, and `initGui()` sweeps stale instances before creating new
  ones.
- QGIS 4 / PyQt6 plugin-load failure: the dock area persisted in QSettings
  is an int, which PyQt6 no longer auto-converts to `Qt.DockWidgetArea` —
  now normalised through `_to_dock_widget_area()` (invalid values fall back
  to the right dock) at every `addDockWidget` call, and the enum-vs-int
  dock-area comparison that silently broke tabifying is fixed. A new test
  (`test/test_geoe3_dock_construction.py`) builds the complete dock — all
  panels — on both PyQt5 and PyQt6 images so constructor-time porting
  regressions fail the suite instead of plugin load.

## [2.0.5] - 2026-09-01

### Added

- Environmental-hazard indicators now expose a clickable link to the source
  dataset in the World Bank Data Catalog for the selected hazard (fire,
  flood, landslide, cyclone, drought) (#398).
- Regional analyses now pull population demographics automatically from S2S
  when the population source is S2S — new population-vector processing task
  plus a population-source UI in the analysis aggregation dialog (#431).
- Nighttime Lights supports NOAA threshold classification (fixed Black
  Marble value ranges, 5 classes) alongside Jenks Natural Breaks; the binary
  option was replaced by the NOAA thresholds option (#396).

### Changed

- Flood data sources now work at both analysis scales: the raster (DDH
  0–900) path is available in regional analyses and the S2S path in
  national/local ones, with the S2S join using intersection-MAX; the source
  is auto-derived from the indicator configuration (#423).
- Tree headings are now consistently Title Case (acronym/apostrophe-safe),
  normalised at render time so existing projects' stored model.json is
  unaffected.

### Fixed

- GHSL masking (#420, #421): the GHSL options mask now uses the
  `ghsl_settlements` layer already stored in the study-area GeoPackage
  (clipped and reprojected at project setup) instead of depending on the
  `ghsl_settlements_layer.parquet` download path, so masked scoring no
  longer fails when that file is missing or empty.
- Landslide environmental-hazard scoring in regional analyses was reversed
  and is now corrected (#428).
- Regional S2S Nighttime Lights scoring was inaccurate: NTL classification
  now derives six dynamic classes from the data's own min–max range instead
  of Jenks breaks, so every cell value maps to a class and nothing renders
  unclassified (#424).
- Indicator dropdowns in the factor and dimension aggregation dialogs no
  longer shift left when toggling between indicators (vertical scrollbar
  pinned).
- Environmental-hazards datasource rows are better balanced: the source link
  sits beside the file selector, the layer combo is width-capped, and rows
  no longer hug the table border.
- Clicking the GeoE3 Score node now re-shows the last run result — the masked
  score when a mask is active — instead of always reverting to the raw
  score.

## [2.1.0] - 2026-07-13

### Added

- GeoPackage self-healing module (`geest.core.gpkg_doctor`) that detects and
  repairs, in place, the corruption classes seen in the field: stale WAL
  journals, duplicated schema objects (`trigger ... already exists` /
  malformed database schema errors caused by historic write races), and
  structural btree damage (repaired via a rebuild, keeping the corrupt
  original as a `.corrupt-<timestamp>.bak` file).
- Automatic GeoPackage health checks (run in a background task so the UI
  never blocks): on project open, after every workflow run completes, and at
  the end of study area creation.
- Self-heal-and-retry in workflow CRS resolution, so an analysis run against
  a corrupted study area GeoPackage repairs it and continues instead of
  failing with "Could not determine CRS for study area".
- Unit tests for the self-healing module (`test/test_gpkg_doctor.py`).

### Fixed

- Root cause of study area GeoPackage corruption: `SQLITE_USE_OGR_VFS=YES`
  was set process-wide during study area creation. The OGR VSI file layer
  does not implement SQLite file locking, so concurrent write connections
  could interleave page writes unprotected, producing duplicated
  `sqlite_master` pages ("trigger rtree_..._delete already exists"). The
  option is now forced off.

## [2.0.4] - earlier

- See git history for changes prior to the introduction of this changelog.
