# Sharing Your Results

!!! abstract "Learning objective"
    By the end of this page you'll be able to get GeoE3's raw grid
    results out of QGIS (as a vector or raster layer, or exported to
    CSV), and know where every file an analysis produced actually lives
    on disk.

One last thing worth showing is how to access the raw data that's
produced. GeoE3 adds layer groups to your project with a nested structure
similar to the model tree. You can see all the outputs for each
dimension, and each one shows the details relating to it. Right-click
over any node and you'll see a whole bunch of menu items starting with
**Add** (the same right-click menu introduced on [The
Interface](interface.md#right-click-to-interact-with-items)):

- **Add GeoE3 Score to Map**: either a vector grid or a raster grid.
  If you want to work with the vector grid, you can go and look in its
  attribute table and see all of the indices that were calculated across
  the whole study area. Export this to a CSV, take it to your AI
  application or a spreadsheet, and do further numerical interpretation
  using that software.
- **Add GeoE3 Aggregates to Map**: the subnational breakdown, like you
  saw in the PDF report. If you use the **Identify** tool you can click
  on any one of these and see the area name and the majority score,
  basically the highest score for the region.
- There are more products in the menu too: outputs masked by job
  opportunities, the global human settlements layer used for the
  settlements masking, and so on.
- **Open Working Directory** takes you to the place where all of the
  analytical outputs were produced, including the reports and all of the
  data sets that were made during the analysis.

## The study area grid

The foundation underneath every one of these outputs is the
`study_area/` GeoPackage created back when you [created the
project](interface.md#what-happens-next-the-study-area-grid): the
regular grid (hexagons for a regional analysis, square cells for
national or local) that every indicator, factor, dimension and the final
GeoE3 Score is calculated against. You can hand that GeoPackage to a
colleague who wants to build their own analysis on the same spatial
framework.

!!! success "Recap"
    - The raw grid is yours to use beyond QGIS. Add it as a vector
      layer and export its attribute table to CSV for further analysis
      elsewhere.
    - **Add GeoE3 Aggregates to Map** gets you the subnational
      breakdown; the **Identify** tool reads off each region's name and
      majority score.
    - **Open Working Directory** gets you straight to every file this
      analysis produced, including the `study_area/` GeoPackage every
      output is built on.

That should get you up and running with the basics of using the GeoE3
plugin, from an empty QGIS install through to a finished, reportable
analysis. There are more things you can do beyond this walkthrough: the
[Legacy Detailed Reference](../about/legacy-detailed-reference.md) covers
a few individual factors in more granular detail, and
[About](../about/index.md) has the background on the framework this tool
implements.

If you'd like to get in touch (feedback, questions, or to help), the
[Acknowledgements](../about/acknowledgements.md) page has contact details
for the team.
