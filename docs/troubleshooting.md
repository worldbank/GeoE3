# Troubleshooting

GeoE3 checks a few things before it lets you load a project, run the
whole analysis, run only the incomplete indicators, or run a single
indicator: that the project folder itself is usable, that the study
area grid actually covers your whole study area, that the network
layer is set when something you're about to run actually needs it, and
that your indicator's data source is usable.

When one of these checks fails, you'll see a message like the ones
below in the info panel at the bottom of the tree - never a popup.
Each situation has its own icon, so once you've seen one you'll
recognise it again at a glance.

| Icon | Situation | What it means | What to do |
|---|---|---|---|
| ![Working directory problem](images/icons/integrity-working-dir.svg){ width="20" } | **"The analysis folder at `/path/to/project` is not writable"** (or "no longer exists") | GeoE3 can't read or write your project's files - the folder was moved, deleted, or you no longer have permission to write to it. | Restore the folder, or re-open the project from its new location. Nothing can run until this is fixed. |
| ![Grid incomplete](images/icons/integrity-grid-incomplete.svg){ width="20" } | **"Your study area grid is not complete"** | The analysis grid covering your study area is empty, or missing cells for one or more of its areas - usually because grid generation was interrupted. | Re-run study area creation for this project. Nothing can run until the grid is rebuilt - every indicator scores against it. |
| ![Network layer missing](images/icons/integrity-network-layer.svg){ width="20" } | **"Your network layer is not set. Click here to configure."** | At least one indicator you're about to run needs a road network layer, and none is set (or the one that was set can no longer be found). | Open the Network Layer panel and load or choose a network layer. This only blocks the indicators that actually need one - everything else can still run. |
| ![Model corrupted](images/icons/integrity-model-corrupt.svg){ width="20" } | **"The data model for this study area is corrupted and no backup could be used to repair it"** | `model.json` - the file holding your whole project's configuration - couldn't be read, and no usable backup was found either. | This is rare: GeoE3 keeps a backup (`model.json.bak`) of your configuration every time it saves, specifically to recover from this. If you see this message, your project folder's `model.json` and `model.json.bak` are both unusable - restore either file from your own backups if you have one. |
| ![Model repaired](images/icons/integrity-model-repaired.svg){ width="20" } | **"The data model for this project was corrupted. We restored your last automatically-saved backup..."** | `model.json` couldn't be read, so GeoE3 restored it from `model.json.bak` - the copy it kept from your last successful save. | Check your indicator configuration - anything you changed *after* that last save won't be in the restored copy. This is informational, not blocking: your project is usable again. |
| ![Datasource invalid](images/icons/integrity-datasource-invalid.svg){ width="20" } | **"'&lt;Indicator&gt;' was skipped — configure its data source and run it again"** | That one indicator's configured data source can't actually be opened (the file moved, the layer is broken, or nothing valid was ever set). | Open that indicator and reconfigure its data source. Only that indicator is skipped - the rest of the run continues. |

!!! note
    Everything above is about whether GeoE3 can run at all - not whether
    an indicator is *configured*. A perfectly healthy project can still
    show indicators as "Not yet configured" or "Disabled" in the tree;
    see [The Interface](training/interface.md) for those status icons.
