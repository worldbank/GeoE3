# Video Script: GeoE3 Orientation

**Purpose**: Sent ahead of the live 2-hour workshop, or watched standalone
by anyone starting GeoE3 solo. Explains what the tool does, what
participants need to prepare, and what the workshop will cover — so
everyone arrives ready to follow along rather than catching up.

**Target length**: 13–15 minutes
**Tone**: Calm, practical, screen-recording led. Talk over a live QGIS
session wherever possible rather than static slides.
**Companion materials**: `geoe3-training-session.md` (slide deck),
`docs/training/index.md` (written walkthrough)

---

## [00:00–00:45] Cold Open — What GeoE3 Does

**VISUAL**: GeoE3 Score map, full screen, a finished analysis (use the
Saint Lucia or Portugal example already in the docs).

> This is a finished GeoE3 analysis. Every cell on this map — every
> hexagon or square, depending on the scale — has a score from 0 to 5
> for how enabling the local environment is for women's economic
> participation. Dark red means very low enablement. Bright blue means
> highly enabling.
>
> By the end of today's session, you'll have built a map like this one,
> for a country or region of your own choosing, from a blank QGIS
> install.

**VISUAL CUE**: Cut to title card — "GeoE3: Orientation"

---

## [00:45–01:45] Who This Is For, and Why It Exists

**VISUAL**: About page / framework diagram, or a slow pan across the
GeoE3 logo and World Bank Group credit.

> Quick bit of context before we dive in. GeoE3 was built to put a
> genuinely rigorous spatial framework — the World Bank's GeoWEAF
> methodology — into the hands of people who need to act on it, without
> requiring a team of GIS specialists or a custom data pipeline for
> every country.
>
> If you're a planner, a researcher, a gender specialist, or an analyst
> who needs to identify *where* economic enablement is weakest, and
> *why*, this tool does the heavy spatial lifting so you can focus on
> the interpretation and the intervention. You don't need to be a QGIS
> expert. If you can click through a wizard and fill in a few
> dialogs, you can run a full analysis.

---

## [01:45–03:00] What GeoE3 Actually Measures

**VISUAL**: The three-dimension diagram (scoring_pipeline.svg), or the
model tree in QGIS with the three top-level dimensions expanded.

> GeoE3 — the Geospatial Enabling Environments for Employment tool —
> implements the World Bank's GeoWEAF framework: the Geospatial Women's
> Employment Analytical Framework. It combines three kinds of evidence
> into one score:
>
> **Contextual** — the laws and policies that shape workplace
> discrimination, financial inclusion, and regulatory frameworks. These
> don't vary across a country; they're national.
>
> **Accessibility** — how easily people reach the services they need
> day to day: childcare, healthcare, education, transport, financial
> services. This one's spatial — it changes block by block.
>
> **Place Characterization** — safety, walkability, environmental
> hazard exposure, and more, at the level of the place itself.
>
> Every one of those gets broken down further into factors, and factors
> into indicators — the actual calculated layers. We'll cover that tree
> structure properly in the workshop. For now, just know: three
> dimensions, each built from several factors, each factor from one or
> more indicators, and sixteen factors across the three dimensions in
> total.

---

## [03:00–04:45] What You Need Before the Session

**VISUAL**: Screen-recorded install steps — Plugin Manager, searching
"GEOE3", Install Plugin.

> Here's what to have ready before the live session, so we're not
> spending workshop time on installs.
>
> One: **QGIS**, version 3.x — 3.28 or later is recommended. It's free,
> it's open source, download it from qgis.org if you don't already have
> it.
>
> Two: the **GeoE3 plugin** itself. Open QGIS, go to Plugins, Manage and
> Install Plugins, switch to the All tab, search for GEOE3, and click
> Install Plugin. [pause on screen while this happens] Once it's
> installed, you'll see a new GEOE3 icon in the toolbar.
>
> Three: **internet access**. Several steps — OpenStreetMap downloads,
> population data, humanitarian datasets — fetch data live during the
> session.
>
> Four: **disk space**. A national-scale analysis can use several
> gigabytes of working files, so make sure you've got room before you
> start.
>
> Five: an **empty folder** on your machine, ready to be your project
> folder. GeoE3 treats this folder as entirely its own, so don't point
> it at something with other files already in it.
>
> And six — this one's not technical — have a **country or region in
> mind**. Somewhere you know a bit about, ideally somewhere you can find
> a boundary layer and some local data for. We'll pick this for real at
> the start of the session, so there's no harm thinking about it now.

---

## [04:45–07:00] A Tour of the Interface (No Clicking Yet)

**VISUAL**: Open GeoE3, click through the welcome pages, land on project
selection, then the model tree of an already-configured project.

> Let's take a quick look at where we're headed, without doing anything
> yet.
>
> Click the GeoE3 icon, and the panel docks on the right. A short
> welcome, then you're asked to open an existing project, start a new
> one, or import a country pack someone's shared with you. In the
> workshop, we're creating a new project from scratch.
>
> Creating one asks for a scale — regional, national, or local, each
> with a different default grid size — a boundary layer, and whether
> you want the Women's Enabling Environments framework or the generic
> version. We're doing Women's Enabling Environments.
>
> Once that's confirmed, GeoE3 builds something called the **study area
> grid** — a regular grid of cells (hexagons at regional scale, squares
> otherwise) covering your whole study area. This grid is the
> foundation everything else gets calculated against. You'll watch this
> happen live in the session; it can take a few minutes depending on
> the size of your country. When it finishes, a Study Area Report pops
> up automatically, telling you how many cells were created and where
> every generated file lives on disk — useful to know the first time,
> easy to ignore after that.
>
> Then you land here — the model tree. Three dimensions, factors
> underneath each, indicators underneath those. Every row has a status
> icon telling you whether it's configured, run, or still needs
> attention. This tree is where you'll spend most of the session.

---

## [07:00–09:00] The One Pattern You'll Use All Day

**VISUAL**: Double-click an indicator, show the dialog, point out the
Use checkbox, weight fields, OK button, then right-click → Run Item
Workflow.

> Here's the single most important thing to understand before the
> session: every item in that tree — indicator, factor, dimension, or
> the whole analysis — is configured exactly the same way.
>
> Double-click it. If it's an indicator, point it at some data — a
> layer you've already loaded, a file you browse to, or for a lot of
> OpenStreetMap-backed indicators, a button that downloads it for you
> directly. If it's a factor, a dimension, or the analysis itself,
> you're assigning weights instead — how much each child item counts
> toward the parent's score. Those weights have to add up to one; if
> they don't, they turn red and you can't confirm.
>
> If you don't have data for something, don't force a bad guess in —
> untick its Use checkbox, and press Balance Weights to redistribute
> evenly across what's left.
>
> Click OK. Then right-click the item and choose Run Item Workflow. A
> green checkmark means it worked.
>
> That's it. That's the whole pattern. You'll use it dozens of times —
> once per indicator, once per factor, once per dimension, once for the
> whole analysis — and it never changes. Learn it once here, and the
> rest of the session is just applying it, dimension by dimension.

---

## [09:00–10:45] Where the Data Comes From

**VISUAL**: Split — an indicator's "Download from OSM" button, then a
quick look at the Geofabrik/GADM/HDX/WorldPop pages.

> A reasonable question at this point: where does all this data
> actually come from?
>
> Some of it's fully automatic — a lot of indicators have a download
> button built right into their configuration dialog, pulling from
> OpenStreetMap or Space2Stats directly. If you're working at regional
> scale, GeoE3 can even prefetch everything in one go during project
> setup.
>
> Some of it you fetch yourself from open sources — Geofabrik for OSM
> extracts, GADM for administrative boundaries, the Humanitarian Data
> Exchange for crisis and conflict data, WorldPop for population broken
> down by age and sex.
>
> And a handful of Contextual indicators — the legal and policy ones —
> are entered as a single researched number you look up yourself, from
> published indices like the World Bank's Women, Business and the Law
> database, or the EPLEX database for the generic, non-gender-specific
> version of the analysis.
>
> We'll cover exactly where to get each one in the session. For now,
> just know there's no single place you have to go — it's a mix, and
> the tool tells you which kind each indicator needs.

---

## [10:45–12:30] What a Finished Run Gets You

**VISUAL**: Finished GeoE3 Score map, bivariate legend grid image, a
glimpse of the PDF report scrolling.

> Once every dimension is configured, you run the whole thing — one
> button, Run All — and it works through every indicator, factor and
> dimension in order. For a large country at fine resolution, this can
> take a while; it's designed to run in the background, and it saves
> progress continuously, so a crash or an interrupted session doesn't
> lose your work. Reopen the project and click Run Incomplete, and it
> picks up exactly where it left off.
>
> What you get at the end: a GeoE3 Score map on the same 0 to 5 scale
> for every single output. If you've supplied population data, you also
> get GeoE3 by Population — a richer, 15-class view combining
> enablement with population density, so you can see not just where
> enablement is low, but where it's low *and* a lot of people actually
> live.
>
> You also get a full PDF analysis report automatically — credits,
> legends, every dimension broken down, a correlation heatmap between
> factors, and the methodology and weights actually used in your run.
> And everything's exportable: the raw grid as CSV for a spreadsheet or
> another GIS tool, or the whole project bundled into a single
> GeoPackage you can hand to a colleague to rebuild from scratch.
>
> We'll walk through reading all of this properly in the review video
> after everyone's had a chance to run their own analysis.

---

## [12:30–14:00] What To Expect From the Session Itself

**VISUAL**: The agenda slide from the deck.

> Quick logistics for the live session. It's two hours, hands-on — bring
> a laptop with QGIS and the plugin already installed, and follow along
> rather than just watching. We'll move through the interface, the
> model, getting data, the configuration pattern, then each of the
> three dimensions in turn, hands-on the whole way. Partway through,
> we'll kick off the full analysis run and take a short break while it
> processes, then come back to interpret the results together, look at
> the report, and cover how to share what you've built.
>
> You don't need to finish configuring every single factor live — one
> worked example per dimension is enough to learn the pattern. You can
> finish the rest afterward using the slide deck or the full written
> walkthrough as a reference; it's always up to date at
> worldbank.github.io/GeoE3.

---

## [14:00–15:00] Close

**VISUAL**: Logo, Kartoza credit, links.

> So — before we meet: QGIS installed, the GeoE3 plugin installed, a
> country or region in mind, enough disk space, and an empty folder
> ready to go. That's everything you need.
>
> See you in the session. We'll go from a blank install to a finished,
> reportable analysis in two hours.

**END CARD**: GeoE3 — worldbank.github.io/GeoE3 — Made with 💗 by
Kartoza
