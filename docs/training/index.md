# Training Walkthrough

This walkthrough is presented by Tim, lead developer of the GeoE3
plugin, built under contract to the World Bank.

GeoE3 is a tool to help identify areas where we can improve employment
and economic outcomes, specifically for women, but it can also be used
generically to look at the local population of a country and understand
which areas need intervention to improve people's economic outcomes.

This section walks you through from absolute beginning, starting from
zero through to having a complete project set up and running for your
country of choice, illustrated with screenshots captured step by step.
Work through it top to bottom the first time; after that, use it as a
reference for whichever dimension you're configuring.

## Course outline

1. [Installation](installation.md): install QGIS, then the GeoE3 plugin.
2. [The Interface](interface.md): open the plugin, create a project,
   and get oriented in the model tree (a right-clickable tree of
   dimensions, factors and indicators).
3. [The Model](the-model.md): what an indicator, factor, dimension and
   analysis actually are, how weights aggregate one into the next, and
   the 0–5 Likert scale every score lands on.
4. [Processor Types](processor-types.md): the computation techniques an
   indicator can use to turn raw data into a score, straight from the
   PDF report's own Methodology section.
5. [Getting Data](datacollection.md): every way GeoE3 sources its input
   data, from fully automatic downloads to manual research.
6. [Configuring Items](configuring-items.md): the one generic pattern
   for configuring any item in the tree.
7. ![](../images/topics/contextual.svg){ width="20" style="vertical-align:middle;margin-right:0.3rem;" } [Contextual Dimension](contextual.md): the national and regional factors
   that set the baseline for enablement.
8. ![](../images/topics/accessibility.svg){ width="20" style="vertical-align:middle;margin-right:0.3rem;" } [Accessibility Dimension](accessibility.md): service areas for
   childcare, healthcare, education and other daily needs.
9. ![](../images/topics/place_characterization.svg){ width="20" style="vertical-align:middle;margin-right:0.3rem;" } [Place Characterization Dimension](placecharacterization.md): safety,
   walkability and hazard exposure at the place level.
10. ![](../images/topics/geoe3_score.svg){ width="20" style="vertical-align:middle;margin-right:0.3rem;" } [Running the Analysis](running-the-analysis.md): Run All vs Run
    Incomplete, and recovering from a crash partway through a long run.
11. ![](../images/topics/geoe3_score.svg){ width="20" style="vertical-align:middle;margin-right:0.3rem;" } [Viewing Your Results](insights.md): interpret the final enablement
    score, drill into any dimension, factor or indicator.
12. [The Analysis Report](report.md): read the PDF report the tool
    generates after every run, section by section.
13. [Sharing Your Results](sharing.md): export the underlying grid and
    the study area GeoPackage for use beyond QGIS.

## Related formal training

The World Bank Group Institute periodically runs a scheduled online course,
*Geographic Considerations in Evaluating Women's Employment Opportunities*,
covering the same GeoWEAF framework with animated videos, quizzes and a
certificate of completion. It's aimed at urban planners, policymakers,
gender specialists, researchers and social development professionals.
Current enrollment dates are published on the
[WBG Institute](https://wbginstitute.learnworlds.com/home) site; subscribe to
the [Institute for Economic Development Newsletter](https://www.worldbank.org/en/newsletter-subscription?ifiifed=true)
to be notified of upcoming sessions.
