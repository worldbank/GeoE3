# Video Script: Reviewing Your GeoE3 Results

**Purpose**: Watched after the workshop (or after any solo run), once a
participant has a completed analysis. Walks through interpreting the
GeoE3 Score, the bivariate legend, the PDF report, and what to do next.
Doesn't repeat configuration steps — this is entirely about reading
results you already have.

**Target length**: 12–15 minutes
**Tone**: Analytical but accessible — this is the "so what does it
mean" video, aimed at someone looking at their own finished map for the
first time.
**Companion materials**: `docs/training/insights.md`, `docs/training/
report.md`, `docs/training/sharing.md`
**Example dataset used throughout**: a Regional-scale Women's Enabling
Environments analysis of Portugal (the same example used in the
published PDF report walkthrough) — swap in your own country's map if
recording this for a specific cohort.

---

## [00:00–01:00] Cold Open — You've Got a Map, Now What?

**VISUAL**: A completed GeoE3 Score map, full screen.

> If you're watching this, you've just finished running a GeoE3
> analysis — or you're about to, and want to know what you'll be
> looking at. Either way: this video is entirely about interpretation.
> Not how to configure anything, not how to run anything — just how to
> read what GeoE3 just gave you, and what to do with it.
>
> We'll go through four things: the score map and its legend, the
> bivariate population view, the PDF report GeoE3 generates
> automatically, and how to get the underlying data out for your own
> analysis.

---

## [01:00–03:00] Reading the GeoE3 Score

**VISUAL**: The model tree with GeoE3 Score highlighted, then the map
itself, panning across a few contrasting regions.

> Start here: the GeoE3 Score layer. Right-click it in the tree and
> choose Add to Map if it isn't already loaded — it usually is,
> automatically, once the run finishes.
>
> Every cell is scored 0 to 5. Deep red is very low enablement. Orange
> is low. Yellow, moderate. Green, enabling. Blue, highly enabling. This
> is the same scale every single indicator, factor and dimension in
> GeoE3 uses — so once you've learned to read it here, you can read it
> everywhere in the tool.
>
> One thing worth knowing up front: a **blank** cell isn't the same as
> a score of **zero**. Blank means outside the study area, or no data
> was available for that cell. A genuine zero means the measured
> service is actually out of reach — say, a cell with no road network
> access at all for a routing-based indicator. Don't read a blank patch
> on the map as "terrible" — check whether it's blank or genuinely red
> first.
>
> Notice the layer group has **Mutually Exclusive Group** turned on —
> switching one output's visibility on automatically turns the others
> off. That's deliberate, so your comparisons between outputs stay
> clean rather than overlapping into a mess.

---

## [03:00–05:30] The Bivariate Legend: Enablement × Population

**VISUAL**: The bivariate legend grid image, then the GeoE3 by
Population map layer.

> If you supplied a population layer — either auto-fetched from
> Space2Stats or your own, say from WorldPop — you unlock a second,
> richer output: **GeoE3 by Population**.
>
> This is the one that trips people up the first time, so let's slow
> down. It's a 5 by 3 grid: five enablement levels across the bottom,
> three population density tiers — low, medium, high — up the side.
> That's fifteen classes in total.
>
> Read it like this: **enablement reads across**, from very low
> enablement on the left to highly enabling on the right. **Population
> density reads down** — or up, depending on how it's oriented on your
> screen right now — from low density to high density.
>
> So the deep red, bottom-left corner is the combination you'd most
> want to act on first in most policy contexts: **low enablement, and a
> lot of people living there**. The bright blue, opposite corner is low
> enablement's mirror image: high enablement, high population — places
> already working well for a lot of people.
>
> The genuinely interesting cells are often the ones that aren't at
> either extreme: moderate enablement with high population density, for
> instance, tells you there's real leverage — a modest intervention
> there affects a lot of people, which might matter more for overall
> impact than a severe score in a sparsely populated cell.
>
> This same 15-class legend appears again if you configured a
> subnational boundary layer and used **Add GeoE3 Aggregates to Map** —
> same colours, same logic, just aggregated up to administrative
> regions instead of individual grid cells.

---

## [05:30–08:00] Walking Through the PDF Report

**VISUAL**: Right-click the analysis node → Show Analysis Report, then
scroll through the generated PDF.

> Every run also produces a full PDF report automatically. Right-click
> the analysis node and choose Show Analysis Report — it takes a few
> minutes to build, so kick it off and keep working while you wait.
>
> It opens with **credits** — the funding partners and exactly which
> data sources contributed to this specific run: OpenStreetMap,
> OpenRouteService, GHSL, Ookla, Space2Stats, ACLED, VIIRS night-time
> lights, whatever you supplied yourself.
>
> Then the legends are explained properly — the 0 to 5 scale, and the
> bivariate one we just covered — followed by an **Analysis Overview**:
> every output you generated, with the proportion of cells falling into
> each enablement class. In this Portugal example, most of the country
> sits in moderate enablement, with pockets of both high and low.
>
> Next, **every dimension and factor gets its own page** — full map,
> description, and smaller maps for each factor underneath it.
> Contextual factors come out as one flat colour across the whole
> country, because they're national-level scores with no spatial
> variation — that's expected, not a mistake.
>
> If you configured a subnational boundary, you'll also see **factor
> score patterns** as sparklines, a **low scores** page showing which
> dimension most often limits the worst-scoring cells — in this
> Portugal run, it's Accessibility, meaning distance to services, not
> legislation, is the single biggest lever for raising those cells a
> class — and a **settlement and hazard patterns** page comparing
> average scores across the whole study area versus just the populated
> parts.

---

## [08:00–10:00] Reading the Correlation Heatmap

**VISUAL**: The factor correlation heatmap page, zoomed in.

> One page is worth real attention: the **factor correlation heatmap**.
> It's a grid of every factor against every other factor, coloured from
> deep navy to deep red.
>
> **Deep navy** means two factors tend to score high in the same
> places — they move together. That's useful: it suggests a shared root
> cause, and a single intervention might move both factors at once.
>
> **Deep red** means the opposite — one factor tends to score high
> exactly where the other scores low. In the Portugal example,
> environmental hazards and access to public transport are negatively
> correlated: areas with good transport access tend to have lower
> hazard exposure, or vice versa.
>
> **Pale or white** cells mean no real relationship between those two
> factors.
>
> The diagonal — every factor against itself — is always deepest navy.
> That's not a finding, it's just a factor perfectly correlating with
> itself. Ignore the diagonal.
>
> If you turned on the **Subnational score matrix** setting — Settings,
> Options, GeoE3, off by default — you'll also get a region-by-factor
> colour grid, with factors identified by number rather than name, so
> keep the key page handy while reading it. A column that's one solid
> colour all the way down is almost always a flat Contextual score, not
> a bug.

---

## [10:00–12:00] Getting the Data Out

**VISUAL**: Right-click GeoE3 Score → Add to Map (vector), open
attribute table, export to CSV. Then Bundle Input Data to GeoPackage.

> Last piece: getting this out of QGIS for use elsewhere.
>
> Add GeoE3 Score to Map as a **vector** layer — its attribute table has
> every index calculated across the whole study area. Open the
> attribute table, export to CSV, and take it into a spreadsheet, a BI
> tool, or an AI-assisted analysis workflow for further numerical work
> beyond what QGIS itself does well.
>
> If you've got a subnational boundary configured, Add GeoE3 Aggregates
> to Map gives you the regional breakdown, and the Identify tool reads
> off any region's name and majority score directly.
>
> And if you want to hand the whole thing to a colleague — not just the
> results, but the inputs and the model itself — right-click the GeoE3
> Score node and choose **Bundle Input Data to GeoPackage**. That single
> file lets anyone rebuild your exact project with **Import a Country
> Pack**, ready to run, no further setup.
>
> Everything this analysis produced — the reports, every dataset
> generated along the way — lives in your project's working directory.
> Open Working Directory from the right-click menu gets you there
> directly.

---

## [12:00–13:30] Three Common Misreadings

**VISUAL**: Side-by-side comparisons — a blank vs. a red cell, a flat
Contextual map, a sparsely-populated red cell vs. a densely-populated
yellow one.

> Three things people misread the first time they look at their own
> results.
>
> One: **blank isn't zero**, covered already, but worth repeating
> because it's the single most common misread. Check the legend, not
> just the colour.
>
> Two: **a flat national colour on a Contextual factor is correct, not
> broken**. If Workplace Discrimination shows the exact same shade
> everywhere in the country, that's because it's a National Index Score
> — one researched number, filled across every cell. It's supposed to
> look like that.
>
> Three: **a severe score in a sparsely populated cell matters less, in
> most policy contexts, than a moderate score in a dense one**. This is
> exactly why the bivariate legend exists — a glance at the plain
> GeoE3 Score map alone can't tell you that; you need the population
> dimension to see it.

---

## [13:30–14:30] Close — What to Do With This

**VISUAL**: Full GeoE3 Score map again, then logo and credit.

> So: a score map you can trust the scale of everywhere in the tool, a
> bivariate view that tells you not just *where* enablement is low but
> *how many people* that actually affects, a full PDF report that
> explains its own methodology, and a correlation heatmap that points
> toward which interventions might move more than one factor at once.
>
> That's everything you need to take this from "I ran an analysis" to
> "I can explain what this analysis means" — to a colleague, a
> policymaker, or yourself six months from now.
>
> Full written detail on every page of the report, and everything else
> covered in the live session, is always up to date at
> worldbank.github.io/GeoE3.

**END CARD**: GeoE3 — worldbank.github.io/GeoE3 — Made with 💗 by
Kartoza
