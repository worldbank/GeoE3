# GeoE3 QGIS Plugin Architecture

## Executive Summary

GeoE3 (Geospatial Enabling Environments for Employment Tool) is a sophisticated QGIS plugin that provides a comprehensive geospatial analysis framework for assessing opportunities and constraints related to employment, safety, connectivity, and well-being. The plugin implements a layered architecture with a hierarchical data model, asynchronous workflow orchestration, and extensive integration with external geospatial services.

---

## 1. Plugin Entry Points and Lifecycle

### 1.1 Plugin Class: `GeoE3Plugin`

**File:** `/geest/__init__.py`

The `GeoE3Plugin` class is the QGIS plugin interface defined by the `classFactory()` function.

#### Key Attributes:
- `iface`: QGIS interface object
- `run_action`: Toolbar action for showing/hiding the dock widget
- `debug_action`: Developer-mode action for debugging
- `dock_widget`: Main `GeoE3Dock` instance
- `profiler`, `profiler_action`, `save_profile_action`: cProfile-based profiling tools
- `options_factory`: Instance of `GeoE3OptionsFactory` for plugin settings

#### Lifecycle Methods:

**`initGui()`**
- Creates and adds toolbar icon for the main plugin action
- Initializes the main dock widget (`GeoE3Dock`) with resource path to `model.json`
- Sets the dock widget's object name to "GeoE3DockWidget" for geometry persistence
- Configures dock widget features (closable, movable, floatable)
- Connects `QgsProject.readProject` signal to `qgis_project_changed()` for automatic project loading
- Restores dock widget geometry from QSettings
- Registers the options factory for plugin settings dialog
- Installs `CanvasOverlayFilter` event filter on map canvas
- In developer mode, adds debug toolbar actions (debug mode, run tests, run single test, profiler)
- Applies environment variable overrides: `GEOE3_DEBUG`, `GEOE3_EXPERIMENTAL`

**`unload()`**
- Saves dock widget geometry to QSettings
- Disconnects project change signal
- Removes all toolbar icons and cleans up actions
- Unregisters the options factory
- Removes canvas overlay filter
- Deletes the dock widget

#### Developer Features:

**`debug()`** - Starts debugpy debug server on port 9000
**`toggle_profiler()` / `save_profile_results()`** - cProfile-based profiling with KCacheGrind integration
**`run_tests()` / `run_single_test()`** - Unit test discovery and execution in Python console

### 1.2 Map Canvas Overlay System

**File:** `/geest/__init__.py` (class `CanvasOverlayFilter`)

Manages event filtering for map canvas to clear overlay data on left-click:
- Listens for `QEvent.Type.MouseButtonPress` with `Qt.MouseButton.LeftButton`
- Clears QSettings entries: `geoe3/overlay_label`, `geoe3/pie_data`

### 1.3 Logging Infrastructure

- Log file path: `${GEOE3_LOG}` env var or `${GEEST_LOG}` or temp directory
- Log rotation: By datestamp (e.g., `geoe3_logfile_20260713.log`)
- Level: DEBUG (file) with PyQt uic suppressed to WARNING
- Entry point logs plugin version and QGIS version on startup

---

## 2. GUI Panel System

### 2.1 Main Dock Widget: `GeoE3Dock`

**File:** `/geest/gui/geoe3_dock.py`

Manages a stacked widget with 10 sequential panels for project creation and analysis workflow.

#### Panel Indices:
```python
INTRO_PANEL = 0              # Welcome/intro screen
CREDITS_PANEL = 1            # Credits/about screen
SETUP_PANEL = 2              # Project type selection (local/regional)
OPEN_PROJECT_PANEL = 3       # Browse and load existing projects
CREATE_PROJECT_PANEL = 4     # Create new project with AOI/grid
S2S_PANEL = 5                # Space2Stats data configuration (regional only)
ORS_PANEL = 6                # OpenRouteService API configuration
ROAD_NETWORK_PANEL = 7       # Road network layer selection
TREE_PANEL = 8               # Main analysis tree (dimensions/factors/indicators)
HELP_PANEL = 9               # Help and documentation
```

#### Key Features:

**Constructor (`__init__`)**
- Initializes main widget with `QStackedWidget` container
- Loads theme background image and stylesheet
- Creates all 10 panel widgets early to enable signal connections
- Wires inter-panel navigation signals (e.g., "next" button on INTRO_PANEL connects to CREDITS_PANEL)
- Initializes message bar (`QgsMessageBar`) at top for error/warning notifications

**Panel Navigation Logic**
- Uses Qt signals (`pyqtSignal`) for backward-compatible navigation
- Example: `intro_widget.switch_to_next_tab.connect(lambda: self.stacked_widget.setCurrentIndex(CREDITS_PANEL))`
- Dynamic routing: S2S_PANEL is skipped for local-scale projects; ORS_PANEL routing depends on `analysis_scale` in `model.json`

**Project Loading (`qgis_project_changed`)**
- Triggered when QGIS project changes (signal from main plugin)
- Checks for associated GeoE3 project: computes hash of QGIS project file path, looks up in QSettings
- If found and `model.json` exists, loads project into TreePanel and switches to TREE_PANEL
- Restores saved road network layer path from model
- Sets QGIS project path for later reference

**QGIS Project Association (`open_associated_qgis_project`)**
- Reads `qgis_project_path` from model.json
- Opens associated QGIS project if it differs from current project
- Sets `_suppress_qgis_project_changed` flag to prevent signal loop

**Conditional Panel Rendering (`_is_regional_project_flow`)**
- Reads `analysis_scale` from `model.json` to determine project type
- Returns True if `analysis_scale == "regional"`
- Used to route S2S_PANEL (regional) vs. direct to ORS_PANEL (local)

#### Panel-Specific Setup:

**`on_panel_changed(index)`**
- Handles setup tasks when switching to each panel:
  - INTRO_PANEL, CREDITS_PANEL, CREATE_PROJECT_PANEL: Set font size
  - ROAD_NETWORK_PANEL: Set working directory, reference layer, CRS from CREATE_PROJECT_PANEL
  - S2S_PANEL: Validate regional project flow, set working directory

#### Message Bar Integration

Shared `QgsMessageBar` passed to panels for notifications:
- RoadNetworkPanel and TreePanel use it directly
- Used for warnings like "Missing working directory"

### 2.2 Panel Details

#### IntroPanel (`/geest/gui/panels/intro_panel.py`)
- Welcome screen with GeoE3 branding and project information
- Signal: `switch_to_next_tab` → CREDITS_PANEL

#### CreditsPanel (`/geest/gui/panels/credits_panel.py`)
- Attribution and acknowledgments
- Signals: `switch_to_previous_tab` → INTRO_PANEL, `switch_to_next_tab` → SETUP_PANEL

#### SetupPanel (`/geest/gui/panels/setup_panel.py`)
- Project type selection (local vs. regional analysis)
- Signals: `switch_to_load_project_tab` → OPEN_PROJECT_PANEL, `switch_to_create_project_tab` → CREATE_PROJECT_PANEL (with reset), `switch_to_previous_tab` → CREDITS_PANEL

#### OpenProjectPanel (`/geest/gui/panels/open_project_panel.py`)
- File browser for loading existing GeoE3 projects
- Signals: `switch_to_previous_tab` → SETUP_PANEL, `switch_to_next_tab` → TREE_PANEL, `set_working_directory`, `project_loaded`
- Emits `project_loaded` after setting `working_dir` property

#### CreateProjectPanel (`/geest/gui/panels/create_project_panel.py`)
- Interactive project creation with:
  - Study area definition (draw/import/upload AOI polygon)
  - Grid cell size selection (in meters)
  - Coordinate reference system (CRS) selection
  - Reference layer (for CRS extraction)
- Signals: `switch_to_previous_tab` → SETUP_PANEL, `switch_to_next_tab` → (S2S_PANEL if regional, else ORS_PANEL), `working_directory_changed`
- Method: `reset_for_new_project_flow()` clears UI state for new projects
- Properties: `working_dir`, `reference_layer()`, `crs(working_directory=None)`

#### S2SPanel (`/geest/gui/panels/s2s_panel.py`)
- Space2Stats API configuration (regional analysis only)
- Dataset selection: NTL (nighttime lights), environmental hazards, education
- Signals: `switch_to_previous_tab` → CREATE_PROJECT_PANEL, `switch_to_next_tab` → ORS_PANEL
- Method: `set_working_directory(path)`

#### OrsPanel (`/geest/gui/panels/ors_panel.py`)
- OpenRouteService API key configuration
- Service capabilities check
- Signals: `switch_to_previous_tab` → (S2S_PANEL if regional, else CREATE_PROJECT_PANEL), `switch_to_next_tab` → ROAD_NETWORK_PANEL

#### RoadNetworkPanel (`/geest/gui/panels/road_network_panel.py`)
- Road network and cycle path layer selection
- Saves layers to working directory
- Signals: `switch_to_previous_tab` → ORS_PANEL, `switch_to_next_tab` → TREE_PANEL, `road_network_layer_path_changed`
- Methods: `set_working_directory()`, `set_reference_layer()`, `set_crs()`, `restore_layer_from_path()`, `road_network_layer_path()`
- Passes message bar reference for error notifications

#### TreePanel (`/geest/gui/panels/tree_panel.py`)
- **Central analysis interface** (described in detail in Section 2.3)
- Hierarchical tree view of analysis structure (dimensions → factors → indicators)
- Run button to execute workflows
- Signals: `switch_to_next_tab` → HELP_PANEL, `switch_to_network_tab`, `switch_to_ors_tab`, `switch_to_setup_tab`

#### HelpPanel (`/geest/gui/panels/help_panel.py`)
- Help documentation and FAQs
- Signal: `switch_to_previous_tab` → TREE_PANEL

### 2.3 TreePanel: Core Analysis Interface

**File:** `/geest/gui/panels/tree_panel.py`

The TreePanel is the central hub for analysis configuration and execution.

#### Key Components:

**JsonTreeModel & JsonTreeView**
- Hierarchical view of `model.json` structure
- Three-tier hierarchy:
  1. **Dimension** (e.g., "Accessibility", "Safety") — Bold icon/font
  2. **Factor** (e.g., "Distance to Market", "Police Presence") — Italic font
  3. **Indicator** (e.g., calculated analysis result) — Terminal leaf node
- Each node has attributes:
  - `name`, `status` (e.g., "Not Run", "Running", "Complete"), `weight`
  - `attributes` dict (analysis_mode, datasource config, output paths, etc.)
  - `guid` (UUID for tracking across sessions)
- Model serializes back to JSON for persistence

**Run Controls**
- `run_incomplete_only()` checkbox: Skip indicators already marked "complete"
- Run button: Triggers `_run_analysis()` → queues workflows in `WorkflowQueueManager`
- Progress bar: Shows queue status (e.g., "3 of 10 tasks running")

**Status Display**
- Tree node visual indicators: Color-coded status badges
- Log window: Real-time workflow output
- Message bar: Error/warning notifications from workflows

**Context Menu Actions**
- Open associated layer in QGIS
- Configure workflow parameters
- Delete/clear results
- Export results

**Working Directory Management**
- Property: `self.working_directory`
- Contains subdirectories:
  - `study_area/` — study_area.gpkg (grid, AOI, clip polygons)
  - `model.json` — analysis configuration
  - `workflows/` — subdirectories per indicator execution
  - Layer outputs (GeoPackage tables or raster files)

#### Workflow Execution Pipeline

**User clicks "Run":**
1. Collects items to run (filters by completion status if `run_only_incomplete=True`)
2. For each item, calls `self.queue_manager.add_workflow(item, cell_size_m, analysis_scale)`
3. Calls `self.queue_manager.start_processing()` to launch async task execution
4. WorkflowQueue processes jobs concurrently (up to `concurrent_tasks` limit)
5. Each job emits progress → model updates tree node status
6. On completion, tree node marked "complete" and output layer added to QGIS canvas

#### Advanced Features:

**Grid-based Aggregation**
- `_run_grid_aggregation()`: Aggregates indicator results by grid cell
- Writes raster values to GeoPackage grid column via `write_raster_values_to_grid()`

**Opportunity Mapping**
- `_run_opportunities()`: Identifies grid cells meeting criteria
- Uses raster algebra with `OpportunitiesMaskProcessor` and related tasks

**Study Area Report**
- `_run_study_area_report()`: Generates PDF summary via `StudyAreaReport` class

**Subnational Aggregation**
- Aggregates results by admin boundary or custom polygon layer
- Task: `SubnationalAggregationProcessingTask`

---

## 3. Core Orchestration: Workflow Queue System

### 3.1 WorkflowQueueManager

**File:** `/geest/core/workflow_queue_manager.py`

Top-level orchestrator for task execution. Manages a single `WorkflowQueue` instance and acts as the public interface.

#### Key Responsibilities:

**Signal Emissions**
- `processing_completed` — Emitted when all queued tasks finish
- `processing_error(str)` — Emitted if any task fails

**Public Methods**

| Method | Purpose |
|--------|---------|
| `add_workflow(item, cell_size_m, analysis_scale)` | Wraps item in a `WorkflowJob`, adds to queue |
| `add_task(task)` | Adds any `QgsTask` to queue |
| `start_processing()` | Begins async execution |
| `start_processing_in_foreground()` | Debug mode: runs workflows sequentially in main thread |
| `cancel_processing()` | Cancels all queued/active tasks |

**Constructor**
- Takes optional `pool_size` parameter (defaults to None = read from settings dynamically)
- Creates `WorkflowQueue` instance
- Connects queue signals to manager's signal handlers

#### Example Usage (from TreePanel):

```python
self.queue_manager = WorkflowQueueManager(pool_size=None)  # Dynamic pool size
self.queue_manager.add_workflow(item, cell_size_m=100.0, analysis_scale="local")
self.queue_manager.processing_completed.connect(self._on_workflow_complete)
self.queue_manager.start_processing()
```

### 3.2 WorkflowQueue

**File:** `/geest/core/workflow_queue.py`

Manages a queue of `WorkflowJob` tasks and thread pool concurrency.

#### Architecture:

**Thread Safety**
- `job_queue: List[WorkflowJob]` — Pending jobs (main thread only)
- `active_tasks: Dict[str, WorkflowJob]` — In-progress tasks (protected by `QMutex`)
- `_active_tasks_mutex` — Exclusive lock for active_tasks dictionary
- Pattern: Acquire lock, read/modify, release lock before emitting signals

**Concurrency Control**

```python
def process_queue(self):
    # Step 1: Check queue with lock
    locker = QMutexLocker(self._active_tasks_mutex)
    active_count = self._active_queue_size_unsafe()
    locker = None  # Release lock immediately

    # Step 2: Compute free threads (no lock)
    pool_size = self.get_effective_pool_size()  # Reads 'concurrent_tasks' setting
    free_threads = pool_size - active_count

    # Step 3: Submit jobs to QGIS task manager
    for _ in range(free_threads):
        if not self.job_queue:
            break
        job = self.job_queue.pop(0)

        # Acquire lock only for dictionary write
        locker = QMutexLocker(self._active_tasks_mutex)
        self.active_tasks[job.description()] = job
        locker = None

        # Connect signals and add task (no lock)
        QgsApplication.taskManager().addTask(job)

    self.update_status()
```

**Dynamic Pool Sizing**
- `get_effective_pool_size()` reads `concurrent_tasks` setting on every batch
- Allows users to change parallelism without restarting QGIS

#### Signal Emissions

| Signal | Purpose |
|--------|---------|
| `status_changed` | Queue state changed (task added/removed) |
| `processing_completed(bool)` | All tasks done; bool=True if success |
| `status_message(str)` | Informational log message |
| `processing_error(str)` | Task error detected |

#### Lifecycle

1. **add_job(job)** — Appends to job_queue if not duplicate
2. **start_processing()** → **process_queue()** — Begin extracting jobs
3. **task_completed(job_name)** → **finalize_task(job_name)** — Remove from active_tasks, increment total_completed
4. **process_queue()** recursively called until job_queue empty AND active_tasks empty
5. Emits `processing_completed(True)` when finished

#### Statistics

- `total_queue_size` — Cumulative job count
- `total_completed` — Completed job count
- `active_queue_size()` — Thread-safe accessor for active task count

### 3.3 WorkflowJob

**File:** `/geest/core/workflow_job.py`

Represents a single analysis task. Extends `QgsTask` for integration with QGIS task manager.

#### Key Responsibilities:

**Workflow Creation**
- Constructor accepts `JsonTreeItem` (reference, not copy)
- Uses `WorkflowFactory.create_workflow()` to instantiate appropriate workflow class
- Any modifications to `item` during execution directly update the tree

**Progress Reporting**
- Connects workflow's `progressChanged` signal to `updateProgress(float)`
- Workflow updates item status via signals

**Error Handling**
- Connects workflow's `workflowError` signal to `error_occurred` signal
- Emits `error_occurred(str)` on exception

**Profiling (Developer Mode)**
- Class-level `_profiling_enabled` flag
- Per-job cProfile instance created if enabled
- Accumulates stats in `_combined_profiler`
- `save_profiling_stats(output_file=None)` saves to .prof file for SnakeViz analysis

**Caching Support**
- `@cacheable(maxsize=128)` decorator for method-level caching
- Custom `make_hashable()` function converts unhashable types to tuples
- `clear_all_caches()` class method clears all registered method caches

#### Execution Model (`run()` method)

```python
def run(self) -> bool:
    # 1. Setup profiling if enabled
    if self.__class__._profiling_enabled:
        self._profiler = cProfile.Profile()
        self._profiler.enable()

    # 2. Execute workflow
    try:
        self.job_started.emit()
        result = self._workflow.execute()
        if result:
            log_message(f"Workflow {self.description()} completed.")
            return True
        else:
            log_message(f"Workflow {self.description()} failed.")
            return False
    except Exception as e:
        log_message(f"Error: {e}", level=Qgis.Critical)
        self.error_occurred.emit(f"Error in {self.description()}: {str(e)}")
        return False
    finally:
        # 3. Finalize profiling
        if self._profiling_active:
            self._profiler.disable()
            # Accumulate to combined_profiler for class-level stats
            stats = pstats.Stats(self._profiler)
            self.__class__._combined_profiler.add(stats)
            self.__class__._jobs_profiled += 1
```

#### Signals

| Signal | Payload | Purpose |
|--------|---------|---------|
| `job_queued` | — | Job added to queue |
| `job_started` | — | Execution beginning |
| `job_canceled` | — | User cancellation |
| `job_finished(bool)` | success | Execution complete |
| `error_occurred(str)` | message | Error during execution |
| `status_message(str)` | message | Progress update for UI |

### 3.4 WorkflowFactory

**File:** `/geest/core/workflow_factory.py`

Factory pattern: maps `analysis_mode` attribute → concrete workflow class.

#### Workflow Mapping

| `analysis_mode` | Workflow Class | Purpose |
|-----------------|----------------|---------|
| `use_index_score` | `DefaultIndexScoreWorkflow` | Calculate weighted composite score |
| `use_contextual_index_score` | `ContextualIndexScoreWorkflow` | Score with contextual weighting |
| `use_eplex_score` | `EPLEXWorkflow` | EPLEX employment proxy score |
| `use_index_score_with_ookla` | `IndexScoreWithOoklaWorkflow` | Score with Ookla speed data |
| `use_index_score_with_ghsl` | `IndexScoreWithGHSLWorkflow` | Score with GHSL settlement data |
| `use_multi_buffer_point` | `MultiBufferDistancesORSWorkflow` (or `NativeWorkflow`) | Multi-radius distance analysis (ORS or QGIS native) |
| `use_single_buffer_point` | `SinglePointBufferWorkflow` | Single-radius buffer |
| `use_point_per_cell` | `PointPerCellWorkflow` | Count/aggregate point features per grid cell |
| `use_polyline_per_cell` | `PolylinePerCellWorkflow` | Intersect polyline features per grid cell |
| `use_osm_transport_polyline_per_cell` | `OsmTransportPolylinePerCellWorkflow` | OSM road length per cell |
| `use_polygon_per_cell` | `PolygonPerCellWorkflow` | Polygon feature overlap per grid cell |
| `factor_aggregation` | `FactorAggregationWorkflow` | Combine factor results → dimension score |
| `dimension_aggregation` | `DimensionAggregationWorkflow` | Combine dimension scores → overall score |
| `analysis_aggregation` | `AnalysisAggregationWorkflow` | Final aggregation (map algebra) |
| `use_csv_to_point_layer` | `AcledImpactWorkflow` | Convert ACLED conflict data to points |
| `use_classify_polygon_into_classes` | `ClassifiedPolygonWorkflow` | Categorize polygon data |
| `use_classify_safety_polygon_into_classes` | `SafetyPolygonWorkflow` | Safety-specific polygon classification |
| `use_nighttime_lights` | `SafetyRasterWorkflow` | Process NTL raster (S2S download) |
| `use_environmental_hazards` | `RasterReclassificationWorkflow` | Reclassify environmental hazard rasters |
| `use_street_lights` | `StreetLightsBufferWorkflow` | Street light buffer analysis |
| `Do Not Use` | `DontUseWorkflow` | No-op (placeholder) |

#### Constructor Logic

```python
def create_workflow(self, item, cell_size_m, analysis_scale, feedback, context):
    attributes = item.attributes()
    analysis_mode = attributes.get("analysis_mode", "")

    if analysis_mode == "use_index_score":
        return DefaultIndexScoreWorkflow(item, cell_size_m, analysis_scale, feedback, context)
    # ... (30+ modes) ...
    elif analysis_mode == "use_multi_buffer_point":
        # Dynamic selection: check setting
        use_ors = setting(key="use_ors_for_accessibility", default=False)
        if use_ors:
            return MultiBufferDistancesORSWorkflow(...)
        else:
            return MultiBufferDistancesNativeWorkflow(...)
    # ... etc.
```

---

## 4. JSON Tree Model and Data Hierarchy

### 4.1 JsonTreeItem

**File:** `/geest/core/json_tree_item.py`

Represents a single node in the analysis hierarchy. Designed to be thread-safe without inheriting from `QObject`.

#### Critical Constraint

**NOT a QObject**: JsonTreeItem is explicitly NOT a QObject subclass to remain thread-safe. It is passed by reference to background workflow threads and must not trigger Qt signals/slots.

#### Data Structure

```python
class JsonTreeItem:
    def __init__(self, data, role, guid=None, parent=None):
        self.parentItem = parent                      # Parent node
        self.itemData = data                           # [name, status, weight, attributes_dict]
        self.childItems = []                           # Child nodes
        self.role = role                               # 'root', 'dimension', 'factor', 'indicator'
        self.guid = guid or str(uuid.uuid4())          # Unique identifier
        self._lock = QReadWriteLock()                  # Thread safety
        self.font_color = QColor(Qt.GlobalColor.black) # UI color

        # Icons and fonts for each role
        self.dimension_icon, self.factor_icon, self.indicator_icon
        self.dimension_font, self.factor_font

        self._visible = True                           # Visibility in tree
        self._enabled = True                           # Enabled (not greyed out)
```

#### Thread-Safe Access

**Atomic Context Manager**
```python
with item.atomicAttributeUpdate() as attrs:
    attrs["result"] = "/path/to/output.tif"
    attrs["status"] = "Complete"
    # Lock released on exit
```

**Safe Getters**
```python
def getAttribute(self, key, default=None):
    self._lock.lockForRead()
    try:
        return self.itemData[3].get(key, default)
    finally:
        self._lock.unlock()

def attributesSnapshot(self):
    self._lock.lockForRead()
    try:
        return dict(self.itemData[3]) if len(self.itemData) > 3 else {}
    finally:
        self._lock.unlock()
```

#### Role-Based Rendering

| Role | Icon | Font | Purpose |
|------|------|------|---------|
| `root` | N/A | Normal | Invisible root node |
| `dimension` | Dimension icon | Bold | Top-level grouping (e.g., "Accessibility") |
| `factor` | Factor icon | Italic | Middle-level component (e.g., "Distance to Market") |
| `indicator` | Indicator icon | Normal | Leaf node with analysis result |

#### Attributes Dictionary

The 4th element of `itemData` is a dict containing workflow configuration:

```python
{
    "name": "Distance to Market",
    "status": "Not Run",  # or "Running", "Complete", "Error"
    "weight": 1.0,
    "analysis_mode": "use_multi_buffer_point",
    "datasource_type": "vector_and_field",
    "datasource": "/path/to/markets.shp",
    "field": "market_type",
    "buffer_distances": [5000, 10000, 15000],
    "result": "/path/to/output.tif",
    "result_file": "/path/to/study_area/study_area_grid_distance_to_market",
    "execution_start_time": "2026-07-13T10:30:00",
    "execution_end_time": "2026-07-13T10:35:42",
    # ... 20+ analysis-specific attributes
}
```

### 4.2 JsonTreeModel

**File:** `/geest/gui/views/treeview.py`

Qt model adapter for the JSON tree structure. Implements `QAbstractItemModel` interface.

#### Hierarchy Representation

```
Root (JsonTreeModel.rootItem)
└── Analysis (created from model.json root attributes)
    ├── Dimension 1 (e.g., "Accessibility")
    │   ├── Factor 1.1 (e.g., "Distance to Market")
    │   │   └── Indicator 1.1.1 (calculated result)
    │   └── Factor 1.2 (e.g., "Public Transport Access")
    │       └── Indicator 1.2.1 (calculated result)
    ├── Dimension 2 (e.g., "Safety")
    │   ├── Factor 2.1
    │   │   └── Indicator 2.1.1
    │   └── Factor 2.2
    │       └── Indicator 2.2.1
    └── Dimension 3 (Aggregation nodes)
        ├── Factor Aggregation Score
        ├── Dimension Aggregation Score
        └── Analysis Aggregation Score
```

#### Initialization from JSON

**File: `model.json` structure**
```json
{
  "guid": "<UUID>",
  "analysis_name": "My Analysis",
  "description": "Description of analysis",
  "analysis_scale": "local",
  "analysis_cell_size_m": 100,
  "working_folder": "/path/to/project",
  "road_network_layer_path": "/path/to/network.shp",
  "result": "",
  "execution_start_time": "",
  "execution_end_time": "",
  "result_file": "",

  "dimensions": [
    {
      "guid": "<UUID>",
      "name": "Accessibility",
      "status": "Not Run",
      "weight": 1.0,
      "attributes": { ... },
      "factors": [
        {
          "guid": "<UUID>",
          "name": "Distance to Market",
          "status": "Not Run",
          "weight": 0.5,
          "attributes": {
            "analysis_mode": "use_multi_buffer_point",
            "datasource_type": "vector_and_field",
            "datasource": "...",
            ...
          },
          "indicators": [ ... ]  # Usually empty; populated by workflows
        }
      ]
    }
  ]
}
```

**`loadJsonData(json_data)` process**
1. Create Analysis item from root attributes
2. Iterate dimensions, create Dimension items
3. For each dimension, iterate factors, create Factor items
4. For each factor, iterate indicators, create Indicator items
5. Set parent-child relationships via `childItems` list

#### Model Methods (QAbstractItemModel)

| Method | Purpose |
|--------|---------|
| `rowCount(parent)` | Return len(parent.childItems) |
| `columnCount(parent)` | Return 3 (Name, Status, Weight) |
| `index(row, column, parent)` | Return QModelIndex for child |
| `parent(index)` | Return QModelIndex of parent |
| `data(index, role)` | Return cell value based on Qt::ItemDataRole |
| `setData(index, value, role)` | Update cell value, emit dataChanged |
| `flags(index)` | Return ItemIsSelectable \| ItemIsEnabled \| ItemIsEditable |
| `headerData(section, orientation, role)` | Return column names |

#### Serialization

**`toJson()`** — Reconstruct model.json structure from tree
- Walks tree, collects attributes from each node
- Recursively builds dimensions → factors → indicators structure
- Returns dict compatible with model.json schema

---

## 5. Supporting Subsystems

### 5.1 Settings System

**File:** `/geest/core/settings.py`

Thin wrapper around `QSettings` with project/global scoping.

#### Key Functions

**`setting(key, default=None, prefer_project_setting=False, qsettings=None)`**
- Retrieves value from QSettings (ESMAP/GeoE3 scope)
- Falls back to default if key not found
- Optional type casting via expected_type parameter
- If `prefer_project_setting=True`, checks `QgsProject.instance()` settings first

**`set_setting(key, value, qsettings=None)`**
- Stores value in QSettings
- Handles OrderedDict → dict conversion for safe storage

**`deep_convert_dict(value)`**
- Recursively converts OrderedDict → dict for QSettings compatibility

#### Common Settings

| Key | Default | Purpose |
|-----|---------|---------|
| `ors_key` | "" | OpenRouteService API key |
| `use_ors_for_accessibility` | False | Use ORS vs. QGIS native for distance analysis |
| `concurrent_tasks` | 1 | Max parallel workflows |
| `developer_mode` | 0 | Enable debug toolbar actions |
| `enable_caching` | 1 | Enable method-level LRU caching |
| `verbose_mode` | 0 | Log detailed profiling output |
| `last_working_directory` | "" | Most recent project folder |

### 5.2 Internationalization (i18n)

**File:** `/geest/core/i18n.py`

Translation support via Qt .qm files.

#### Key Functions

**`setup_translation(file_pattern="{}.qm", folder=None)`**
- Detects system locale from QgsSettings
- Searches for .qm file matching locale (e.g., "geoe3_fr_FR.qm")
- Returns (locale_name, file_path) tuple or (locale_name, None)

**`tr(text, context="@default")`**
- Wrapper for `QApplication.translate(context, text)`
- Enables string translation via Qt's translation system

#### Usage
```python
from geest.core.i18n import tr
label = tr("Accessibility", context="GeoE3")  # Translatable string
```

### 5.3 Reports System

**File:** `/geest/core/reports/` (3 classes)

#### BaseReport (`base_report.py`)
Abstract base class for PDF report generation via QGIS Layout.

**Constructor**
```python
def __init__(self, template_path: str, report_name="Report"):
    self.layout = None  # QgsLayout instance
    self.report_name = report_name
    self.template_path = template_path  # Path to .qpt template file
    self.page_descriptions = {}
    self._cleanup_done = False
```

**Key Methods**
- `cleanup()` — Resource cleanup (context manager support)
- `load_template()` — Load QGIS layout from .qpt file
- `add_map()` — Add QgsLayoutItemMap with extent/CRS
- `add_label()` — Add QgsLayoutItemLabel with text
- `add_shape()` — Add QgsLayoutItemShape (legend, title box, etc.)
- `export_pdf(output_path)` — Render to PDF via QgsLayoutExporter

#### StudyAreaReport (`study_area_report.py`)
Summary report with study area extent, grid statistics, data sources.

**Properties**
- Study area extent map
- Grid cell count and statistics
- Data source attribution
- Analysis metadata

#### AnalysisReport (`analysis_report.py`)
Detailed results report with indicator maps and aggregate scores.

**Contents**
- Per-indicator map pages
- Aggregation score visualizations
- Statistical summaries

#### Report Integration

Reports are generated as QgsTask subclasses (e.g., `AnalysisReportTask`) queued alongside workflow tasks.

### 5.4 OSM Downloader System

**File:** `/geest/core/osm_downloaders/`

Multi-class framework for querying and downloading OpenStreetMap data.

#### Class Hierarchy

**`OsmDataDownloaderBase` (`osm_data_downloader_base.py`)**
- Abstract base for all OSM downloaders
- Common methods for query construction, error handling
- Downloads from Overpass API

**Concrete Downloader Classes**
| Class | OSM Query | Purpose |
|-------|-----------|---------|
| `OsmRoadsDownloader` | `way[highway~"^(motorway\|trunk\|...)."]` | All roads |
| `OsmActiveTransportDownloader` | Bicycle infrastructure tags | Cycling/walking routes |
| `OsmCyclewayDownloader` | `way[cycleway=...]` | Dedicated cycleways |
| `OsmPublicTransportDownloader` | `relation[type=route][route~"^(bus\|tram\|...)."]` | Transit routes |
| `OsmHealthFacilityDownloader` | `node[amenity~"^(hospital\|clinic)."]` | Health facilities |
| `OsmEducationDownloader` | `node[amenity~"^(school\|university)."]` | Schools/universities |
| `OsmGroceryDownloader` | `node[shop~"^(supermarket\|market)."]` | Food retail |
| `OsmWaterPointDownloader` | `node[amenity=drinking_water]` | Water points |
| `OsmPharmacyDownloader` | `node[amenity=pharmacy]` | Pharmacies |
| `OsmKindergartenDownloader` | `node[amenity=kindergarten]` | Early childhood |
| `OsmFinancialDownloader` | `node[amenity~"^(bank\|atm)."]` | Banking |
| `OsmGreenSpaceDownloader` | `way[leisure=park]` | Parks/recreation |

**Download Process**
1. Construct Overpass QL query using tags specific to feature type
2. POST to Overpass API via `Downloader` class (wraps QgsFileDownloader)
3. Parse OSM XML response → GeoJSON (via GDAL/OGR)
4. Clip to study area bbox
5. Save to GeoPackage or shapefile

#### Associated Classes

**`OsmDownloadType` (`osm_download_type.py`)**
- Enum-like structure for download categories (roads, public_transport, etc.)

**`OsmDownloaderFactory` (`osm_downloader_factory.py`)**
- Factory pattern: maps download type → downloader class

**`QueryPreparation` (`query_preparation.py`)**
- Constructs Overpass QL from bbox and tag filters
- Handles bbox clipping, query validation

#### Download Integration

Downloads are queued as `OsmDownloaderTask` (QgsTask subclass) in WorkflowQueue.

### 5.5 ORS (OpenRouteService) Client

**File:** `/geest/core/ors_client.py`

HTTP client for OpenRouteService API (distance matrix, isochrone, routing).

#### Key Methods

**`check_api_key()`**
- Reads ORS API key from setting or `ORS_API_KEY` env var
- Raises EnvironmentError if not found

**`make_request(endpoint, params)`**
- Blocking POST request to ORS API (intended for use in background thread)
- Sets Authorization header with API key
- Returns parsed JSON response dict

#### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/v2/matrix/*` | Isochrone/distance matrix (multi-point) |
| `/v2/matrix/{profile}/` | Mode-specific routing (foot, bike, car) |
| `/v2/isochrones/{profile}/` | Time-distance contours |

#### Error Handling

- Raises `EnvironmentError` for missing API key
- Raises `ValueError` for invalid token
- Raises `RuntimeError` for HTTP 404/500 errors
- Logs detailed error messages

### 5.6 Space2Stats (S2S) Client

**File:** `/geest/core/s2s_client.py`

Client for public Space2Stats API (vector summaries for zonal statistics).

#### Key Methods

**`health()`** — Check API availability

**`fields()`** — List available summary fields

**`summary(aoi, geometries, dataset, join_method, fields)`**
- Query Space2Stats for zonal statistics
- `aoi` (dict): GeoJSON geometry or bbox
- `geometries` (list): "point" or "polygon"
- `dataset` (str): Data source (e.g., "urbanization_ghssmod", "viirs_ntl")
- `join_method` (str): "centroid", "within", or "touches"
- `fields` (list): Output field names
- Returns parsed summary statistics

#### Retry Logic

- Exponential backoff with jitter for transient failures (502, 503, 504)
- `max_attempts=4`, `backoff_base_seconds=0.5`

### 5.7 GHSL Downloader & Processor

**Files:** `/geest/core/algorithms/ghsl_downloader.py`, `ghsl_processor.py`

#### GHSLDownloader

Downloads Global Human Settlement Layer raster data from GHSL API.

**Key Methods**
- `download_for_bbox(bbox, output_path)` — Fetch mosaic for bounding box
- Handles retries, tile stitching, coordinate reprojection

#### GHSLProcessor

Converts GHSL settlement raster (classes 1-6) → vector polygons.

**Processing Pipeline**
1. Reclassify raster (consolidate settlement classes)
2. Polygonize (raster → vector)
3. Dissolve small polygons
4. Calculate settlement area metrics

### 5.8 Ookla Downloader

**File:** `/geest/core/algorithms/ookla_downloader.py`

Downloads Ookla broadband speed data (CSV grid).

**Key Methods**
- `download_for_bbox(bbox, output_path)` — Fetch speed grid for area
- Parses CSV format (lon, lat, speed_mbps)
- Converts to GeoPackage point layer

### 5.9 Grid Column Utilities

**File:** `/geest/core/grid_column_utils.py`

Utilities for writing workflow results to study_area_grid GeoPackage layer.

#### Key Functions

**`write_raster_values_to_grid(gpkg_path, layer_name, raster_path, column_name, feedback=None)`**
- Rasterizes grid polygons with raster values
- Writes pixel values back to GeoPackage column
- Handles SQLite WAL lock contention with retry logic

**`rasterize_grid_column(gpkg_path, layer_name, column_name, cell_size_m, output_raster_path, feedback=None)`**
- Converts GeoPackage column → raster via gdal_rasterize
- Produces Float32 GeoTIFF output

**SQLite Write Pragmas**
```python
ds.ExecuteSQL("PRAGMA busy_timeout=10000")     # 10s lock timeout
ds.ExecuteSQL("PRAGMA journal_mode=WAL")       # Write-ahead logging
ds.ExecuteSQL("PRAGMA synchronous=NORMAL")     # Balanced safety/speed
```

### 5.10 GeoPackage Self-Healer (gpkg_doctor)

**File:** `/geest/core/gpkg_doctor.py`

Novel self-healing system for corrupted GeoPackages (SpatiaLite-backed SQLite).

#### Corruption Types Healed

1. **Stale WAL Journals** — Uncheckpointed -wal/-shm files
   - Remedy: `PRAGMA wal_checkpoint(TRUNCATE)`

2. **Duplicate Schema Objects** — Malformed schema btree leaf pages
   - Symptom: `"trigger/index/table 'X' already exists"`
   - Remedy: Byte-level renaming of duplicate entries until schema parseable

3. **Structural Btree Damage** — Out-of-order rowids, corrupted pages
   - Remedy: `VACUUM INTO` rebuild database, atomic swap, keep corrupt backup

#### API

**`heal_geopackage(path: str, log_fn: Callable[[str], None] = None) → HealReport`**
- Returns namedtuple: `HealReport(path, healthy, was_corrupt, actions, errors)`

#### Memory-Efficient Design

- Streams file chunks (8 MiB) for duplicate detection
- Repairs write only bytes being renamed
- Large files never fully read into memory

---

## 6. Algorithms Folder

**Location:** `/geest/core/algorithms/`

Collection of reusable processing tasks and helper functions.

#### Data Processing Processors

| File | Class | Purpose |
|------|-------|---------|
| `features_per_cell_processor.py` | `FeaturesPerCellProcessor` | Count/aggregate point/polygon features per grid cell |
| `polygon_per_cell_processor.py` | `PolygonPerCellProcessor` | Polygon overlap analysis per grid cell |
| `area_iterator.py` | `AreaIterator` | Yields geometries from study area polygons |
| `grid_column_utils.py` | (functions) | Write raster → GeoPackage column |

#### Score & Opportunity Processors

| File | Class | Purpose |
|------|-------|---------|
| `population_processor.py` | `PopulationRasterProcessingTask` | Rasterize population data |
| `opportunities_mask_processor.py` | `OpportunitiesMaskProcessor` | Generate binary opportunity mask raster |
| `opportunities_by_wee_score_processor.py` | `OpportunitiesByWeeScoreProcessingTask` | Score × Opportunity raster algebra |
| `opportunities_by_wee_score_population_processor.py` | `OpportunitiesByWeeScorePopulationProcessingTask` | Score × Opportunity × Population |
| `wee_by_population_score_processor.py` | `WEEByPopulationScoreProcessingTask` | Composite score × population |

#### Geospatial Data Processors

| File | Class | Purpose |
|------|-------|---------|
| `ghsl_downloader.py` | `GHSLDownloader` | Download GHSL settlement layer |
| `ghsl_processor.py` | `GHSLProcessor` | Convert GHSL raster → vector polygons |
| `ookla_downloader.py` | `OoklaDownloader` | Download Ookla broadband speed grid |
| `native_network_analysis_processor.py` | `NativeNetworkAnalysisProcessingTask` | Batch isochrone/distance via QGIS native algorithms |

#### Aggregation Processors

| File | Class | Purpose |
|------|-------|---------|
| `subnational_aggregation_processor.py` | `SubnationalAggregationProcessingTask` | Aggregate grid results by admin boundary |

#### Utility Functions

**`utilities.py` (algorithms)**
- `check_and_reproject_layer()` — Ensure layer CRS matches project
- `combine_rasters_to_vrt()` — Create virtual raster mosaic
- `geometry_to_memory_layer()` — Convert geometry → temporary QgsVectorLayer
- `subset_vector_layer()` — Filter features by attribute/spatial extent

---

## 7. External Dependencies and Services

### 7.1 External APIs

#### OpenRouteService (ORS)

**Endpoint:** `https://api.openrouteservice.org/`

**Usage in GeoE3:**
- Distance matrix: Multi-origin/destination travel times
- Isochrone: Time-based reachability zones (5/10/15 min)
- Routing: Actual route paths for visualization

**Authentication:** API key (set in plugin settings or `ORS_API_KEY` env)

#### OpenStreetMap/Overpass

**Endpoint:** `https://overpass-api.de/api/interpreter` (or custom mirror)

**Usage:**
- Query OSM tags for 15+ feature categories (roads, healthcare, schools, etc.)
- Download clipped to study area bbox
- Convert to GeoJSON via GDAL/OGR

**Features Queried:**
- Roads (motorway, trunk, primary, secondary, tertiary)
- Public transport (bus, tram, rail routes)
- Healthcare (hospitals, clinics)
- Education (schools, universities)
- Services (financial, pharmacy, grocery)
- Water points, green space, active transport infrastructure

#### Space2Stats (S2S)

**Endpoint:** `https://space2stats.ds.io/` (public API)

**Datasets:**
- `urbanization_ghssmod` — GHSL urbanization classes (for education proxy)
- `viirs_ntl_2024` — Nighttime lights (for safety analysis)
- Environmental hazards: Fire, flood, landslide, cyclone, drought risk

**Usage:**
- Vector summaries: Average/sum field values within polygons
- Zonal statistics for study area grid cells

#### GHSL (Global Human Settlement Layer)

**Source:** `https://ghsl.jrc.ec.europa.eu/` (ESA/EC)

**Data:**
- Settlement extent (raster, 10m resolution)
- Population density
- Built-up area classification (6 classes: urban → rural)

**Processing:**
- Download → polygonize → overlay with grid → aggregation

#### Ookla Broadband Speed

**Source:** Ookla speed grid (CSV)

**Data:**
- Average broadband speeds (Mbps) on 0.075° × 0.075° grid (~8 km)

**Usage:**
- Clip to study area → calculate summary statistics per grid cell

### 7.2 ACLED (Armed Conflict Location and Event Data)

**File:** `/geest/core/workflows/acled_impact_workflow.py`

**Source:** `https://acleddata.com/` (conflict incident data)

**Data:**
- CSV with conflict events (location, date, fatalities, etc.)

**Processing:**
- User uploads CSV → convert to point layer → buffer/aggregate by time
- Used for conflict risk overlay with employment opportunity areas

### 7.3 GDAL/QGIS APIs

#### GDAL/OGR

- **`osgeo.gdal`** — Raster processing (reclassify, polygonize, rasterize, VRT)
- **`osgeo.ogr`** — Vector layer access (GeoPackage, Shapefile, GeoJSON)
- **`osgeo.osr`** — Coordinate reference system handling

#### QGIS Core APIs

| Module | Purpose |
|--------|---------|
| `qgis.core` | QgsVectorLayer, QgsRasterLayer, QgsTask, QgsProcessingContext, etc. |
| `qgis.gui` | QgsMapCanvas, QgsMessageBar, QgsLayerTreeModel, etc. |
| `qgis.analysis` | QgsVectorLayerAnalyzer, network analysis |
| `qgis.processing` | Access to Processing (QGIS native) algorithms |

#### Thread Safety

- All QGIS/Qt objects passed to threads are stored in `QgsProcessingContext`
- `QgsProject.instance()` is thread-safe when stored via context
- `JsonTreeItem` is NOT a QObject and remains thread-safe across threads

---

## 8. Component Inventory Table

| Module Path | Responsibility | Key Classes | Key Methods |
|-------------|-----------------|-------------|-------------|
| `geest/__init__.py` | Plugin entry point, lifecycle | `GeoE3Plugin` | `initGui()`, `unload()`, `debug()`, `run()` |
| `geest/gui/geoe3_dock.py` | Main dock widget, panel navigation | `GeoE3Dock` | `__init__()`, `qgis_project_changed()`, `on_panel_changed()` |
| `geest/gui/panels/intro_panel.py` | Welcome screen | `IntroPanel` | Emits: `switch_to_next_tab` |
| `geest/gui/panels/credits_panel.py` | Credits display | `CreditsPanel` | Emits: `switch_to_next_tab`, `switch_to_previous_tab` |
| `geest/gui/panels/setup_panel.py` | Project type selector | `SetupPanel` | Emits: `switch_to_*_tab` |
| `geest/gui/panels/create_project_panel.py` | New project wizard | `CreateProjectPanel` | `working_dir` property, `crs()`, `reference_layer()` |
| `geest/gui/panels/open_project_panel.py` | Project browser | `OpenProjectPanel` | Emits: `project_loaded`, `set_working_directory` |
| `geest/gui/panels/s2s_panel.py` | S2S configuration (regional) | `S2SPanel` | `set_working_directory()` |
| `geest/gui/panels/ors_panel.py` | ORS API configuration | `OrsPanel` | API key setup, health check |
| `geest/gui/panels/road_network_panel.py` | Network layer selection | `RoadNetworkPanel` | `road_network_layer_path()`, `restore_layer_from_path()` |
| `geest/gui/panels/tree_panel.py` | Main analysis interface | `TreePanel` | `_run_analysis()`, properties: `working_directory`, `queue_manager` |
| `geest/gui/views/treeview.py` | Tree model & view | `JsonTreeModel`, `JsonTreeView` | `loadJsonData()`, `toJson()`, Qt model methods |
| `geest/core/workflow_queue_manager.py` | Task orchestration | `WorkflowQueueManager` | `add_workflow()`, `start_processing()`, `cancel_processing()` |
| `geest/core/workflow_queue.py` | Concurrency control | `WorkflowQueue` | `process_queue()`, `add_job()`, `task_completed()` |
| `geest/core/workflow_job.py` | Individual task execution | `WorkflowJob` | `run()`, profiling/caching support |
| `geest/core/workflow_factory.py` | Workflow instantiation | `WorkflowFactory` | `create_workflow()` (factory method) |
| `geest/core/workflows/workflow_base.py` | Abstract workflow base | `WorkflowBase` | `execute()`, signals: `progressChanged`, `statusChanged`, `workflowError` |
| `geest/core/workflows/*.py` (25+ files) | Concrete workflows | `DefaultIndexScoreWorkflow`, `PointPerCellWorkflow`, etc. | Analysis-specific implementations |
| `geest/core/json_tree_item.py` | Tree node with thread safety | `JsonTreeItem` | Thread-safe getters/setters, `atomicAttributeUpdate()` |
| `geest/core/settings.py` | Configuration management | Module functions | `setting()`, `set_setting()` |
| `geest/core/i18n.py` | Translation support | Module functions | `setup_translation()`, `tr()` |
| `geest/core/reports/base_report.py` | PDF report base class | `BaseReport` | `load_template()`, `export_pdf()`, `cleanup()` |
| `geest/core/reports/study_area_report.py` | Study area summary | `StudyAreaReport` | Report generation, map rendering |
| `geest/core/reports/analysis_report.py` | Results report | `AnalysisReport` | Per-indicator maps, statistics |
| `geest/core/osm_downloaders/*.py` (15+ files) | OSM data downloads | `OsmRoadsDownloader`, `OsmHealthFacilityDownloader`, etc. | Feature-specific query construction |
| `geest/core/ors_client.py` | ORS HTTP API | `ORSClient` | `make_request()`, distance/isochrone queries |
| `geest/core/s2s_client.py` | S2S HTTP API | `S2SClient` | `health()`, `fields()`, `summary()` |
| `geest/core/algorithms/ghsl_downloader.py` | GHSL data acquisition | `GHSLDownloader` | `download_for_bbox()` |
| `geest/core/algorithms/ghsl_processor.py` | GHSL raster→vector | `GHSLProcessor` | `process()` |
| `geest/core/algorithms/ookla_downloader.py` | Ookla speed grid | `OoklaDownloader` | `download_for_bbox()` |
| `geest/core/algorithms/native_network_analysis_processor.py` | QGIS isochrone | `NativeNetworkAnalysisProcessingTask` | Batch distance analysis |
| `geest/core/algorithms/population_processor.py` | Population rasterization | `PopulationRasterProcessingTask` | Rasterize population layer |
| `geest/core/algorithms/opportunities_*.py` (3 files) | Opportunity mapping | `OpportunitiesMaskProcessor`, etc. | Raster algebra, masking |
| `geest/core/algorithms/subnational_aggregation_processor.py` | Admin aggregation | `SubnationalAggregationProcessingTask` | Zonal statistics |
| `geest/core/grid_column_utils.py` | Grid output writing | Module functions | `write_raster_values_to_grid()`, `rasterize_grid_column()` |
| `geest/core/gpkg_doctor.py` | GeoPackage repair | `HealReport` (namedtuple), functions | `heal_geopackage()`, `schema_error()` |
| `geest/core/constants.py` | Application constants | Module vars | `APPLICATION_NAME`, S2S field mappings |
| `geest/utilities.py` | Global utilities | Module functions | `log_message()`, `resources_path()`, theme helpers |

---

## 9. Component and Class Diagrams

### 9.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         QGIS Application                             │
│                         (QgsApplication)                             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  GeoE3Plugin    │  (Plugin entry point)
                    │  (classFactory) │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌────────┐         ┌─────────────┐      ┌─────────────┐
   │Message │         │   GeoE3Dock │      │  Options    │
   │Log API │         │ (Stacked    │      │  Factory    │
   │        │         │  Widget)    │      │             │
   └────────┘         └──────┬──────┘      └─────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌──────────┐
   │  Intro  │         │  Setup  │         │ Create   │
   │ Credits │         │  Open   │         │ Project  │
   │  Help   │         │ Project │         │          │
   └─────────┘         └────┬────┘         └────┬─────┘
                            │                  │
                            ▼                  ▼
                       ┌────────────────────────────────┐
                       │  S2S Panel (Regional only)     │
                       │  ORS Panel                     │
                       │  Road Network Panel            │
                       └────────────┬───────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    TreePanel         │
                         │  (Analysis Hub)      │
                         │  - JsonTreeModel     │
                         │  - JsonTreeView      │
                         │  - WFQueueManager    │
                         └──────────┬───────────┘
                                    │
        ┌───────────────────────────┼───────────────────────┐
        │                           │                       │
        ▼                           ▼                       ▼
   ┌────────────────┐      ┌───────────────┐      ┌─────────────┐
   │ Workflow       │      │ Grid/Report   │      │ OSM/S2S/ORS │
   │ Orchestration  │      │ Processing    │      │  Services   │
   │ - QueueMgr     │      │ - Processors  │      │  & APIs     │
   │ - WorkflowJob  │      │ - Grid Utils  │      │             │
   │ - Factory      │      │ - Reports     │      │             │
   └────────┬───────┘      └──────┬────────┘      └──────┬──────┘
            │                     │                     │
            ▼                     ▼                     ▼
   ┌──────────────────────────────────────────────────────────┐
   │  Data & Configuration Layer                              │
   │  - JsonTreeItem (Thread-safe tree nodes)                 │
   │  - Settings (QSettings wrapper)                          │
   │  - Constants                                             │
   │  - I18n (Translation)                                    │
   │  - GDAL/OGR utilities                                    │
   │  - GeoPackage Doctor (healing)                           │
   └──────────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────────┐
   │  External Services                                       │
   │  - OpenRouteService API                                  │
   │  - Space2Stats API                                       │
   │  - Overpass (OpenStreetMap)                              │
   │  - GHSL API                                              │
   │  - Ookla Speed Grid                                      │
   │  - ACLED (Conflict Data)                                 │
   └──────────────────────────────────────────────────────────┘
```

### 9.2 Core Orchestration Class Diagram

```
┌─────────────────────────────────────┐
│     TreePanel                       │
│  ┌─────────────────────────────┐    │
│  │ queue_manager:              │    │
│  │  WorkflowQueueManager       │    │
│  │                             │    │
│  │ Methods:                    │    │
│  │  - _run_analysis()          │    │
│  │  - _on_workflow_complete()  │    │
│  └──────────┬──────────────────┘    │
└─────────────┼────────────────────────┘
              │ (1:1)
              ▼
┌─────────────────────────────────────────────────────┐
│  WorkflowQueueManager                              │
│  ┌──────────────────────────────────────────────┐  │
│  │ - workflow_queue: WorkflowQueue              │  │
│  │ - processing_completed: pyqtSignal           │  │
│  │ - processing_error(str): pyqtSignal          │  │
│  │                                              │  │
│  │ Methods:                                     │  │
│  │  + add_workflow(item, cell_size, scale)     │  │
│  │  + add_task(task: QgsTask)                   │  │
│  │  + start_processing()                        │  │
│  │  + cancel_processing()                       │  │
│  │  + on_processing_completed(success)          │  │
│  │  + on_processing_error(msg)                  │  │
│  └──────────────┬───────────────────────────────┘  │
└────────────────┼────────────────────────────────────┘
                 │ (1:1)
                 ▼
┌──────────────────────────────────────────────────────────┐
│  WorkflowQueue (Thread Pool Manager)                    │
│  ┌────────────────────────────────────────────────────┐ │
│  │ - job_queue: List[WorkflowJob]                     │ │
│  │ - active_tasks: Dict[str, WorkflowJob]             │ │
│  │ - _active_tasks_mutex: QMutex                      │ │
│  │ - thread_pool_size: int                            │ │
│  │ - total_queue_size: int                            │ │
│  │ - total_completed: int                             │ │
│  │                                                    │ │
│  │ Signals:                                           │ │
│  │  - status_changed()                                │ │
│  │  - processing_completed(bool)                      │ │
│  │  - status_message(str)                             │ │
│  │  - processing_error(str)                           │ │
│  │                                                    │ │
│  │ Methods:                                           │ │
│  │  + add_job(job)                                    │ │
│  │  + process_queue()  [concurrent dispatch]          │ │
│  │  + task_completed(job_name)                        │ │
│  │  + finalize_task(job_name)                         │ │
│  │  + get_effective_pool_size()  [dynamic]            │ │
│  │  + active_queue_size()  [thread-safe]              │ │
│  └────────────────┬─────────────────────────────────┘ │
│                   │ (0..*: concurrent)                │
│                   │                                    │
└───────────────────┼────────────────────────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────────────────┐
    │  WorkflowJob (extends QgsTask)                    │
    │  ┌─────────────────────────────────────────────┐  │
    │  │ - item: JsonTreeItem  (reference)           │  │
    │  │ - _workflow: WorkflowBase                   │  │
    │  │ - _feedback: QgsFeedback                    │  │
    │  │ - _profiler: cProfile.Profile               │  │
    │  │ - context: QgsProcessingContext             │  │
    │  │ - cell_size_m: float                        │  │
    │  │ - analysis_scale: str ("local"/"national")  │  │
    │  │                                             │  │
    │  │ Signals:                                    │  │
    │  │  - job_queued()                             │  │
    │  │  - job_started()                            │  │
    │  │  - job_finished(bool)                       │  │
    │  │  - error_occurred(str)                      │  │
    │  │  - status_message(str)                      │  │
    │  │                                             │  │
    │  │ Methods:                                    │  │
    │  │  + run() -> bool  [executes workflow]       │  │
    │  │  + updateProgress(progress: float)          │  │
    │  │  + updateStatus(status: str)                │  │
    │  │  + feedback() -> QgsFeedback                │  │
    │  │  + finished(success: bool)  [callback]      │  │
    │  │  + [class methods]                          │  │
    │  │    - initialize_profiling()                 │  │
    │  │    - save_profiling_stats()                 │  │
    │  │    - clear_all_caches()                     │  │
    │  └──────────────┬────────────────────────────┘   │
    └─────────────────┼────────────────────────────────┘
                      │ (1:1)
                      ▼
        ┌────────────────────────────────────┐
        │  WorkflowBase (Abstract)            │
        │  + execute() -> bool  [abstract]    │
        │  + progressChanged: pyqtSignal      │
        │  + statusChanged: pyqtSignal        │
        │  + workflowError: pyqtSignal        │
        └────┬───────────────────────────────┘
             │ (extends)
             │
        ┌────┴─────────────────────────────────────┐
        │                                          │
        ▼                                          ▼
  ┌──────────────────────────┐  ┌─────────────────────────────┐
  │DefaultIndexScoreWF       │  │PointPerCellWorkflow         │
  │ (weighted composition)   │  │ (count features per cell)   │
  │                          │  │                             │
  │+ execute()               │  │+ execute()                  │
  │+ ...analysis logic...    │  │+ ...spatial intersection... │
  └──────────────────────────┘  └─────────────────────────────┘
        │                              │
        ├────────────────┬─────────────┤ (25+ concrete workflows)
        │                │             │
        ▼                ▼             ▼
    Multi                Polygon    Classification
    Buffer               Per Cell    Workflows
    Workflows            Workflows   ...
```

### 9.3 Data Model Class Diagram

```
┌────────────────────────────────────────────────────┐
│  JsonTreeItem (Thread-Safe Node)                   │
│  - NOT a QObject (thread-safe)                     │
│                                                    │
│ Attributes:                                        │
│  - parentItem: JsonTreeItem                        │
│  - childItems: List[JsonTreeItem]                  │
│  - itemData: [name, status, weight, attributes]   │
│  - role: str  ("root"/"dimension"/"factor"/...)   │
│  - guid: str  (UUID)                               │
│  - _lock: QReadWriteLock  (thread safety)          │
│  - font_color: QColor                              │
│  - _visible, _enabled: bool                        │
│                                                    │
│ Methods:                                           │
│  + getAttribute(key, default) -> Any               │
│  + attributesSnapshot() -> Dict                    │
│  + atomicAttributeUpdate() -> ContextMgr           │
│  + attributesAsMarkdown() -> str                   │
│  + set_visibility(visible: bool)                   │
│  + is_visible() -> bool                            │
│  + set_enabled(enabled: bool)                      │
│  + is_enabled() -> bool                            │
│  + is_only_child() -> bool                         │
│  + visible_row() -> int                            │
│                                                    │
│ Attributes Dict Structure:                         │
│  {                                                 │
│    "name": str,                                    │
│    "status": str,  # "Not Run"/"Running"/...       │
│    "weight": float,                                │
│    "analysis_mode": str,  # Workflow type selector │
│    "datasource_type": str,  # "vector"/"raster"/.. │
│    "datasource": str,  # File path                 │
│    "field": str,  # (if applicable)                │
│    "buffer_distances": List[int],  # (if multi-buf)│
│    "result": str,  # Output file path              │
│    "result_file": str,  # GeoPackage table name    │
│    "execution_start_time": str,  # ISO datetime    │
│    "execution_end_time": str,  # ISO datetime      │
│    ... (20+ analysis-specific keys)                │
│  }                                                 │
└──────────────────────────────────────────────────┘
        ▲
        │ (aggregates)
        │
┌───────┴──────────────────────────────────────────┐
│  JsonTreeModel (Qt Model)                        │
│  - Implements QAbstractItemModel                 │
│  - Renders JsonTreeItem hierarchy as Qt tree     │
│                                                  │
│ Attributes:                                      │
│  - rootItem: JsonTreeItem  (tree root)           │
│  - original_value: Any  (undo support)           │
│                                                  │
│ Signals:                                         │
│  - collapseNodeRequested(object)                 │
│                                                  │
│ Methods:  (Qt Model Interface)                   │
│  + rowCount(parent: QModelIndex) -> int          │
│  + columnCount(parent) -> int                    │
│  + index(row, col, parent) -> QModelIndex        │
│  + parent(index) -> QModelIndex                  │
│  + data(index, role) -> Any                      │
│  + setData(index, value, role) -> bool           │
│  + flags(index) -> Qt.ItemFlags                  │
│  + headerData(section, orient, role) -> Any      │
│                                                  │
│ Methods:  (Tree Serialization)                   │
│  + loadJsonData(json_data: Dict)                 │
│  + toJson() -> Dict  [reconstructs model.json]   │
└────────────────────────────────────────────────┘
        │
        │ (consumed by)
        │
┌───────┴──────────────────────────────────────────┐
│  JsonTreeView (Qt View)                          │
│  - Extends QTreeView                             │
│  - Renders JsonTreeModel with custom colors      │
│  - Connects to TreePanel for actions             │
│                                                  │
│ Signals:                                         │
│  - itemRunRequested(item: JsonTreeItem)          │
│  - itemConfigureRequested(item: JsonTreeItem)    │
│  - itemDeleteRequested(item: JsonTreeItem)       │
│                                                  │
│ Methods:                                         │
│  + setTreeModel(model: JsonTreeModel)            │
│  + contextMenuEvent(event)  [right-click menu]   │
│  + mouseDoubleClickEvent(event)  [edit]          │
│  + keyPressEvent(event)  [delete key, etc.]      │
└────────────────────────────────────────────────┘
```

---

## 10. Execution Flow: User Clicks "Run"

### 10.1 Sequence: Indicator Execution

```
User                TreePanel                WFQueueMgr           WorkflowQueue
  │                    │                         │                    │
  │   Click "Run"       │                         │                    │
  ├─────────────────────>                         │                    │
  │                    │   _run_analysis()       │                    │
  │                    │                         │                    │
  │                    │   For each item:        │                    │
  │                    │   ├─ Collect to-run     │                    │
  │                    │   │                     │                    │
  │                    │   add_workflow(item)    │                    │
  │                    ├────────────────────────>                     │
  │                    │                         │   add_job(job)     │
  │                    │                         ├───────────────────>│
  │                    │                         │                    │
  │                    │                         │  [job appended     │
  │                    │                         │   to job_queue]    │
  │                    │                         │                    │
  │                    │   (repeat for all)      │                    │
  │                    │   ├─ Add workflow       │                    │
  │                    │   ├─ Add workflow       │                    │
  │                    │   └─ Add workflow       │                    │
  │                    │                         │                    │
  │                    │  start_processing()    │                    │
  │                    ├────────────────────────>                     │
  │                    │                         │ start_processing() │
  │                    │                         ├───────────────────>│
  │                    │                         │                    │
  │                    │                         │ process_queue()    │
  │                    │                         │<───────────────────┤
  │                    │                         │                    │
  │                    │                         │  [acquire lock]    │
  │                    │                         │  [check active]    │
  │                    │                         │  [release lock]    │
  │                    │                         │                    │
  │                    │                         │  [pop job 1]       │
  │                    │                         │  [add to active]   │
  │                    │                         │                    │
  │                    │                         │  QgsTask.addTask() │
  │                    │                         ├───────────────────>
  │                    │                         │                   QgsTask
  │                    │                         │                   Manager
  │                    │                         │                    │
  │                    │                         │  [pop job 2]       │
  │                    │                         │  [add to active]   │
  │                    │                         │  QgsTask.addTask() │
  │                    │                         ├───────────────────>
  │                    │                         │
  │                    │                         │  [continue until   │
  │                    │                         │   thread pool full]│
  │                    │                         │
  │                    │  status_message(msg)   │
  │                    │<──────────────────────┤ (status updates)
  │                    │                         │
  │ [Queue message]    │                         │
  │<────────────────────────────────────────────┤
  │                    │                         │
  │                    │  [Workflows run in     │
  │                    │   background threads]  │
  │                    │                         │
  │                    │  progressChanged(0.5)  │
  │                    │<──────────────────────┤
  │                    │  (updates tree node)   │
  │                    │                         │
  │                    │  taskCompleted()       │
  │                    │<──────────────────────┤ (job 1 done)
  │                    │                         │
  │                    │  finalize_task()       │
  │                    │<────────────────────────┤
  │                    │                         │
  │                    │  [update tree node     │
  │                    │   status → "Complete"] │
  │                    │                         │
  │                    │  process_queue()       │
  │                    │<───────────────────────┤ (recursive dispatch)
  │                    │                         │
  │                    │  [pop job 3, add to Q] │
  │                    │  QgsTask.addTask()     │
  │                    │                         ├───────────────────>
  │                    │                         │
  │                    │  [... repeat until all done ...]
  │                    │
  │                    │  processing_completed()│
  │                    │<──────────────────────┤ (all jobs done)
  │                    │                         │
  │ [Workflow complete]│                         │
  │<────────────────────────────────────────────┤
  │                    │                         │
  │ [Export results]   │                         │
  │ [Refresh canvas]   │                         │
  │ [Show summary]     │                         │
  │                    │                         │
  └────────────────────────────────────────────────┘
```

### 10.2 Workflow Execution Detail

```
WorkflowJob.run()
    │
    ├─ [1. Setup profiling if enabled]
    │       └─ cProfile.Profile().enable()
    │
    ├─ [2. Execute workflow]
    │       │
    │       ├─ workflow.execute()  (thread-safe)
    │       │   │
    │       │   ├─ Load input data (vector/raster/API)
    │       │   │
    │       │   ├─ Process data
    │       │   │   ├─ Buffer/intersect operations
    │       │   │   ├─ Raster algebra
    │       │   │   ├─ Spatial joins
    │       │   │   └─ Aggregations
    │       │   │
    │       │   ├─ Emit progressChanged(0.5)
    │       │   │   └─ Relayed to job.updateProgress()
    │       │   │       └─ QgsTask.setProgress(0.5)
    │       │   │           └─ Tree node visual update
    │       │   │
    │       │   ├─ Emit statusChanged("Rasterizing...")
    │       │   │   └─ Relayed to job.updateStatus()
    │       │   │       └─ job.status_message.emit()
    │       │   │           └─ UI progress label update
    │       │   │
    │       │   ├─ Write results to:
    │       │   │   ├─ GeoPackage table (item.attributes["result_file"])
    │       │   │   ├─ Or GeoTIFF raster
    │       │   │   └─ Item updates: item.setAttribute("result", path)
    │       │   │
    │       │   └─ Return True  (success)
    │       │
    │       └─ (On exception)
    │           ├─ Log exception + traceback
    │           ├─ Emit workflowError(msg)
    │           │   └─ Relayed to job.error_occurred.emit(msg)
    │           │       └─ TreePanel shows error in message bar
    │           └─ Return False
    │
    ├─ [3. Finalization & profiling]
    │       ├─ Disable profiler
    │       ├─ Accumulate stats in class-level _combined_profiler
    │       ├─ Save to .prof file if developer mode enabled
    │       └─ Release profiling lock
    │
    └─ [4. Job finished callback]
            └─ finished(success: bool)
                ├─ Emit job_finished(success)
                └─ WorkflowQueue removes from active_tasks
                    └─ Calls process_queue() recursively
                        └─ Submits next job if available
```

### 10.3 Tree Update Mechanism

```
Workflow Result                    JsonTreeItem                    Tree UI
     │                                 │                             │
     └─ item.setAttribute(              │                             │
        "result", "/path/to/output")    │                             │
                                        │                             │
                                    ┌───▼────────┐                    │
                                    │ Atomic     │                    │
                                    │ Write Lock │                    │
                                    └───┬────────┘                    │
                                        │                             │
                                    attributes[                       │
                                    "result"] =                       │
                                    "/path/to/output"                │
                                        │                             │
                                        ├─ status → "Complete"        │
                                        ├─ result_file → "..."        │
                                        └─ execution_end_time → now   │
                                                                      │
                                    ┌─ Read Lock (UI thread)          │
                                    │                                 │
                    (JsonTreeModel reads via getAttribute)            │
                         │                                             │
                         ├─ data(index, DisplayRole)                  │
                         │   └─ Returns attributes["status"]          │
                         │       → QTreeView cell updates color ✓     │
                         │                                             │
                         └─ data(index, DecorationRole)               │
                             └─ Returns appropriate icon              │
                                 → "Complete" badge shown ✓           │
                                                                      │
                                                      │
                                        Canvas Add Layer
                                        (GeoTIFF or GPkg table)
                                                │
                                                ▼
                                           [Layer visible]
```

---

## Conclusion

GeoE3 is a sophisticated, production-grade geospatial analysis plugin built on a layered architecture emphasizing:

1. **Hierarchical Data Model** — JSON tree structure (dimensions → factors → indicators) with thread-safe nodes
2. **Asynchronous Workflow Orchestration** — WorkflowQueueManager + WorkflowQueue for concurrent task execution with dynamic pool sizing
3. **Flexible Workflow Factory** — 25+ concrete workflow classes mapping analysis modes to spatial algorithms
4. **External Service Integration** — ORS, OSM/Overpass, Space2Stats, GHSL, Ookla, ACLED
5. **Robust Data Handling** — GeoPackage self-healing (gpkg_doctor), SQLite WAL pragmas, thread-safe grid column writes
6. **User-Centric GUI** — 10-panel stacked widget with conditional navigation for local vs. regional projects
7. **Developer Support** — Integrated profiling (cProfile + KCacheGrind), debug mode (debugpy), test runner, logging

The architecture prioritizes thread safety, extensibility, and maintainability, enabling researchers and planners to analyze employment and opportunity landscapes at multiple scales.
