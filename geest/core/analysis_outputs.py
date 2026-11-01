# -*- coding: utf-8 -*-
"""The fixed set of analysis-level outputs the GeoE3 Score info panel cycles through.

Pure metadata only - no model.json or GeoPackage access here. The item info
panel (geest/gui/widgets/item_info_panel.py) uses this to render the
carousel; TreePanel (geest/gui/panels/tree_panel.py) is the one that knows
how to check each stop's availability and load its layer, same separation of
concerns the rest of the info panel already follows.
"""

#: One entry per stop, in cycle order. "key" is the stable identifier passed
#: to TreePanel's dispatcher (_load_analysis_output()) and used to look up
#: availability; "icon" is a filename under geest/resources/icons/topics/.
#: "sparkline": False means this stop has no Sparkline page at all (not
#: "not yet computed" - the report itself doesn't draw a normal per-column
#: histogram for either of the two: Job Opportunities Mask is binary, not a
#: 5/15-class score, and GHSL Settlements is a reference layer, not a score
#: surface) - "next" from these two stops' Item view skips straight to the
#: next carousel stop instead of offering a Sparkline step first.
ANALYSIS_OUTPUT_STOPS = [
    {
        "key": "score",
        "label": "GeoE3 Score",
        "icon": "geoe3_score.svg",
        "description": "The overall GeoE3 score for this study area.",
        "sparkline": True,
    },
    {
        "key": "by_population",
        "label": "GeoE3 by Population",
        "icon": "geoe3_by_population.svg",
        "description": "GeoE3 score weighted by where people actually live.",
        "sparkline": True,
    },
    {
        "key": "aggregate",
        "label": "GeoE3 Aggregate",
        "icon": "geoe3_aggregate.svg",
        "description": "GeoE3 scores rolled up to each subnational administrative zone.",
        "sparkline": True,
    },
    {
        "key": "masked",
        "label": "Masked Scores",
        "icon": "geoe3_masked_scores.svg",
        "description": "GeoE3 scores with non-data areas masked out.",
        "sparkline": True,
    },
    {
        "key": "opportunities_mask",
        "label": "Job Opportunities Mask",
        "icon": "job_opportunities_mask.svg",
        "description": "Areas identified as having access to job opportunities.",
        "sparkline": False,
    },
    {
        "key": "ghsl_settlements",
        "label": "GHSL Settlements",
        "icon": "ghsl_settlements.svg",
        "description": "Human settlement footprints from the Global Human Settlement Layer.",
        "sparkline": False,
    },
]
