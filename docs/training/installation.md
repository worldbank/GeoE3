# Installing QGIS &amp; GeoE3

!!! abstract "Learning objective"
    By the end of this page you'll have a working QGIS install with the
    GeoE3 plugin enabled, and know where its settings live if you ever
    need to change the defaults.

GeoE3 runs inside [QGIS](https://www.qgis.org/en/site/) as a regular
plugin, so there's nothing to compile or configure beyond what's
covered here.

## Installing QGIS

- A recent QGIS **3.x** install (QGIS 3.28 or later is recommended).
- Internet access the first time you run an analysis, since several
  processing steps fetch open data (OpenStreetMap, population rasters,
  humanitarian data) on demand.
- Enough disk space for your study area's working files (national-scale
  analyses can use several gigabytes).

## Installing the plugin

Follow the steps below to install the GEOE3 QGIS plugin.

### Step 1: Open the Plugin Manager in QGIS

> - 1. Launch QGIS.
> - 1. Go to **Plugins** > **Manage and Install Plugins…**.

![QGIS Plugin Setup](../images/new%20images/plugins.JPG){ width="50%" }

#### Step 2: Install the Plugin

> - 1. In the **Plugin Manager** window, select the **All** tab in the Plugin Manager.
> - 2. Search for `GEOE3`.
> - 3. Select the plugin and click **Install Plugin**.

![QGIS Plugin Installation](../images/new%20images/Install_page_plugin.png){ width="60%" }

#### Step 3: Verify the Installation and Configure the Tool

> - 1. After installation, check the QGIS toolbar for the new **GEOE3** icon *Show/Hide GEOE3 Panel*.

![GEOE3 Toolbar Icons](../images/new%20images/icons.jpg){ width="40%" }
> - 2. If the icon is not visible, go to **Plugins** > **Manage and Install Plugins…**, then click on the **Installed** tab.
> - 3. In the list, find **Geospatial Enabling Environments for Employment Spatial Tool (GEOE3)** and ensure the checkbox is ticked. The GEOE3 panel should now appear in the QGIS interface.

![QGIS Plugin Installation](../images/new%20images/Install_page_show.png){ width="60%" }

!!! success "Recap"
    - GeoE3 is a regular QGIS plugin, installed from the Plugin Manager.
      Search for GEOE3 under the **All** tab.
    - A toolbar icon and a dockable panel appear once it's installed and
      enabled under the **Installed** tab.
    - The default settings in **Settings → Options → GEOE3 Settings** are
      recommended for most users; chunk size and concurrent tasks are the
      two worth revisiting on a particularly powerful (or weak) machine.

Next: [The Interface](interface.md), opening the plugin, creating your
first project, and getting oriented in the model tree.

![GEOE3 Settings](../images/new%20images/Install_page_settings.png){ width="60%" }
