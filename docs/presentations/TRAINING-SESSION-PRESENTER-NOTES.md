# Presenter Notes: GeoE3 — From Install to Insight

A speaker script for the 2-hour hands-on workshop, keyed to
`geoe3-training-session.md`. Participants should have QGIS and the GeoE3
plugin installed before the session (send the pre-session checklist
email a few days out — see *Before We Start* below).

## Session Structure

**Total slides**: 53
**Estimated time**: 120 minutes
**Format**: Marp slide deck + hands-on QGIS work alongside it
**Audience**: Anyone running their first full GeoE3 analysis — planners,
researchers, GIS analysts. No QGIS expertise assumed, but basic GIS
literacy (layers, attribute tables) helps.

## Timing Guide

| # | Segment | Time | Mode |
|---|---|---|---|
| 1 | The Interface | 15 min | Hands-on |
| 2 | The Model & Processor Types | 10 min | Concept |
| 3 | Getting Data | 10 min | Concept + demo |
| 4 | Configuring Items | 10 min | Hands-on |
| 5 | Contextual Dimension | 10 min | Hands-on |
| 6 | Accessibility Dimension | 10 min | Hands-on |
| 7 | Place Characterization Dimension | 10 min | Hands-on |
| 8 | Running the Analysis (+ break) | 10 min | Hands-on + break |
| 9 | Viewing Your Results | 10 min | Hands-on |
| 10 | The Analysis Report | 5 min | Walkthrough |
| 11 | Sharing Your Results | 5 min | Walkthrough |
| 12 | Wrap-up & Q&A | 5 min | Discussion |

**Buffer**: segments 1–9 run close to live, so expect real sessions to
drift ±10–15 minutes depending on group size and questions. The break
built into segment 8 absorbs most of the slack — compress it if you're
running late, stretch it if you're ahead.

## Pre-Session Checklist (send 2–3 days out)

1. QGIS 3.x installed (3.28+ recommended)
2. GeoE3 plugin installed via Plugins → Manage and Install Plugins…
3. A laptop with internet access
4. An empty folder ready for today's project
5. Ask attendees to pick a country or region they know, in advance —
   decision paralysis on this picked live burns 5+ minutes per session

## Key Messages to Emphasize

1. **One pattern, every level** — configuring an indicator, a factor, a
   dimension, and the analysis itself all use the same dialog pattern.
   Once this clicks, the rest of the session is repetition, not new
   learning.
2. **The study area grid is the foundation** — everything (every
   indicator, every output) is calculated against the same grid created
   in step one. Get this right and everything downstream follows.
3. **0–5, always** — every indicator, factor, dimension and the final
   score land on the same Likert scale. This is what makes combining
   wildly different data types into one number valid.
4. **Exclude, don't fudge** — if a factor has no data, untick **Use**
   and **Balance Weights**. Never leave something half-configured.
5. **Progress is never lost** — **Run Incomplete** picks up exactly
   where a crash or restart left off.

## Recommended Flow

### Opening (5 min)
- Start with the *What We'll Build* slide — set the expectation that
  everyone leaves with a real, finished analysis of their own choosing.
- Run through the *Before We Start* checklist out loud. Fix any gaps
  now; it's far more expensive mid-segment-1.

### Segments 1–7: Interface through the Three Dimensions (65 min)
- **Follow-along, not watch-along.** After every numbered "Hands-On"
  slide, physically stop talking and watch the room do the step. Don't
  race ahead on your own machine.
- Segment 1 (The Interface) is the only segment every participant must
  fully complete in step before moving on — everything after depends on
  the project and study area grid existing. Hold here if anyone's grid
  is still processing.
- Segments 5–7 (the three dimensions) don't need every factor
  configured for every participant — one worked example per dimension
  is enough to teach the pattern. Tell the room explicitly: "configure
  at least one factor per dimension now; fill in the rest after the
  session using today's deck as a reference."

### Segment 8: Running the Analysis (10 min, includes break)
- Get everyone clicking **Run All** (or **Run Incomplete**, if they
  skipped some factors) at roughly the same time — this is the natural
  break point.
- While it churns: **take the 10-minute break live**, don't skip it.
  Large countries at fine resolution can take well past the break
  length; that's fine, let it keep running while segment 9 starts with
  whoever's finished, and loop back for stragglers.

### Segments 9–11: Results, Report, Sharing (20 min)
- Segment 9's bivariate legend slide is worth slowing down on — it's
  the thing people misread most often (axis confusion: which direction
  is enablement, which is population).
- Segment 10 (the Report) and 11 (Sharing) can be a narrated walkthrough
  on the main screen rather than strict follow-along, since by now most
  participants are still waiting on their own run to finish.

### Closing (5 min)
- Land on the *Full Pipeline, One Slide* recap.
- Point to **worldbank.github.io/GeoE3** for the full written
  walkthrough — this is the fallback for anything not finished live.
- Open the floor. Common questions by this point: data sourcing for
  factors they don't have local data for, and how to interpret a
  correlation heatmap.

## Interactive Elements

### Poll Questions (ask at the relevant segment)
1. "Who's used QGIS before?" (Segment 1 open — calibrates your pace)
2. "Who already has a road network downloaded?" (Segment 3, Getting
   Data — tells you if the routing setup needs more time)
3. "Whose run finished during the break?" (Segment 9 open)

### Common Sticking Points
- **Empty folder requirement** — someone will try to reuse a folder
  with files in it. Watch for this during Segment 1.
- **Weights not summing to 1** — shown in red in the dialog; point this
  out proactively the first time someone hits it rather than waiting
  for a raised hand.
- **Travel mode mismatch** — mixing walking and driving across
  Accessibility factors produces incomparable results. Call this out
  explicitly in Segment 6.
- **Bivariate legend axis confusion** — reinforce "enablement reads
  across, population density reads down" every time it comes up.

## Full Detail, By Segment

This script assumes familiarity with the written training docs — the
published walkthrough is the canonical source if you need the exact
wording for any step. Section anchors below match the deck's segment
order:

- Segment 1 → *The Interface*
- Segment 2 → *The Model*, *Processor Types*
- Segment 3 → *Getting Data*
- Segment 4 → *Configuring Items*
- Segment 5 → *Contextual Dimension*
- Segment 6 → *Accessibility Dimension*
- Segment 7 → *Place Characterization Dimension*
- Segment 8 → *Running the Analysis*
- Segment 9 → *Viewing Your Results*
- Segment 10 → *The Analysis Report*
- Segment 11 → *Sharing Your Results*

All live at `docs/training/` in this repository, and published at
**worldbank.github.io/GeoE3**.
