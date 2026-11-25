# -*- coding: utf-8 -*-
"""📦 Methodology reference module.

Static, hand-written reference data for the analysis report's
"Methodology" pages: which real-world computation TECHNIQUE sits behind
each `analysis_mode` an indicator can be configured with, a plain-
language explanation of each technique for a non-GIS reader, and the
SVG illustration that goes with it (geest/resources/methodology/).

Several `analysis_mode` values are mechanically different ways of
doing the SAME underlying technique (e.g. counting points vs counting
line length vs counting polygons are all "tally what's inside the
cell") - they're grouped together here so the report explains the
technique once, then lists which indicators in THIS project use it,
rather than repeating near-identical paragraphs per indicator.
"""

from typing import Optional

#: technique_key -> {"name", "svg", "description"}. Keep descriptions
#: concrete and specific - this is read by policy makers with no GIS
#: background, not by developers.
#:
#: Every "description" below must be hand-written by a human, never
#: AI-generated - this is the plain-language explanation end users and
#: policy makers rely on to understand the methodology, so its wording
#: is a deliberate editorial choice, not a drafting task to delegate.
TECHNIQUES = {
    "index_score": {
        "name": "National Index Score",
        "svg": "index_score.svg",
        "description": (
            "In a national index score analysis we 'flood fill' the study area with "
            "the same value. This is because the index has no spatial variance across the "
            "study area. For example, the legistlative conditions that make the workplace "
            "conducive to women's employment are uniformly applied accross a whole country."
        ),
    },
    "feature_count": {
        "name": "Feature Count",
        "svg": "feature_count.svg",
        "description": (
            "A feature count analysis counts how many of a feature (e.g. transportation stops) "
            "exist in each cell. It then assigns a score to the cell depending on whether "
            "there are none, some or many features in the cells."
        ),
    },
    "distance_buffer": {
        "name": "Straight-Line Distance",
        "svg": "distance_buffer.svg",
        "description": (
            "In theses anlyses we draw a buffer around each point feature and "
            "use that to rank areas more highly if they are within the buffer. "
            "For example, we can rank areas within 2km of a bank more highly "
            "because the people living within the zone around the bank have "
            "accessible access to financial services."
        ),
    },
    "network_isochrone": {
        "name": "Distance by Road",
        "svg": "network_isochrone.svg",
        "description": (
            "In many cases, how accessible a facility is depends on the road network "
            "and the time it takes to traverse the network to reach the facility. "
            "With IsoChrones we can create contour lines around a facility based "
            "on travel time. We do this using a routing analysis to estimate how long "
            "it takes to reach the facility from different parts of the network."
        ),
    },
    "raster_lookup": {
        "name": "Map Value Lookup",
        "svg": "raster_lookup.svg",
        "description": (
            "In some cases, the data we use for the analysis can simply be used 'as is' "
            "we don't need to analyse and interpret it. For example, night time light data "
            "can simply be read from the raster and have its value scaled to 0-5."
        ),
    },
    "zone_classification": {
        "name": "Zone Lookup",
        "svg": "zone_classification.svg",
        "description": (
            "If the data for an indicator is provided as polygon boundaries, we "
            "can treat these boundaries as zones and assign a score to each zone "
            "based on its category. For example, safety polygons can contain a "
            "safety category which we can assign into low-medium-high on the Likert "
            "scale."
        ),
    },
    "population_share": {
        "name": "Population Share",
        "svg": "population_share.svg",
        "description": (
            "If an indicator already has data that is aligned to our analysis grid "
            "we can simply do a spatial join on the data and scale the value into the "
            "range of 0-5."
        ),
    },
    "weighted_feature_average": {
        "name": "Weighted Infrastructure Score",
        "svg": "weighted_feature_average.svg",
        "description": (
            "National-scale Active Transport scores a cell differently to the regional "
            "and local active transport. Whilst regional and local scale use the "
            "single-best-feature found in each cell, the national scale takes the "
            "weighted average of the features in the cell."
        ),
    },
}

#: analysis_mode -> technique_key. Several modes share a technique -
#: see the module docstring. Aggregation-role modes ("factor_aggregation"
#: etc.) and "Do Not Use" deliberately have no entry: they aren't a
#: data-collection technique, they're how already-scored indicators get
#: blended together (covered on the "Scoring Weights" page instead).
ANALYSIS_MODE_TECHNIQUE = {
    "use_index_score": "index_score",
    "use_contextual_index_score": "index_score",
    "use_eplex_score": "index_score",
    "use_index_score_with_ookla": "index_score",
    "use_index_score_with_ghsl": "index_score",
    "use_point_per_cell": "feature_count",
    "use_polyline_per_cell": "feature_count",
    "use_polygon_per_cell": "feature_count",
    "use_osm_transport_polyline_per_cell": "feature_count",
    "use_single_buffer_point": "distance_buffer",
    "use_street_lights": "distance_buffer",
    "use_csv_to_point_layer": "distance_buffer",
    "use_multi_buffer_point": "network_isochrone",
    "use_nighttime_lights": "raster_lookup",
    "use_environmental_hazards": "raster_lookup",
    "use_classify_polygon_into_classes": "zone_classification",
    "use_classify_safety_polygon_into_classes": "zone_classification",
    "use_s2s_urban_rural_share": "population_share",
}

#: analysis_mode -> a one-sentence note on what makes THIS mode's data
#: or scoring differ from its technique siblings - shown alongside the
#: indicator's name on the Methodology page, not repeated in the
#: technique description itself.
ANALYSIS_MODE_NUANCE = {
    "use_index_score_with_ookla": "Only scored where broadband coverage data exists.",
    "use_index_score_with_ghsl": "Only scored inside built-up settlements.",
    "use_osm_transport_polyline_per_cell": ("Combines road and cycle-path data, keeping whichever scores higher."),
    "use_csv_to_point_layer": (
        "Each event type has its own buffer distance; where buffers overlap, " "the higher-impact (closest) value wins."
    ),
    "use_nighttime_lights": (
        "Night-time brightness is used as a proxy for how safe an area feels "
        "after dark, not a direct safety measurement."
    ),
}


#: analysis_mode values where the technique actually used also depends
#: on the project's analysis_scale, not on analysis_mode alone - every
#: scale shares the exact same analysis_mode string in model.json (scale
#: is a project-level setting, not a per-indicator one), so
#: ANALYSIS_MODE_TECHNIQUE can't tell them apart by itself.
#: {analysis_mode: {analysis_scale: technique_key}}
_SCALE_DEPENDENT_TECHNIQUE = {
    "use_osm_transport_polyline_per_cell": {"national": "weighted_feature_average"},
}


def technique_for_analysis_mode(analysis_mode: str) -> Optional[str]:
    """The technique key for an indicator's analysis_mode, or None if
    it isn't a data-collection technique (aggregation roles, "Do Not
    Use", or an analysis_mode added since this reference was written).
    """
    return ANALYSIS_MODE_TECHNIQUE.get(analysis_mode)


def technique_for_indicator(analysis_mode: str, analysis_scale: Optional[str] = None) -> Optional[str]:
    """The technique key actually used for an indicator in THIS project,
    accounting for the handful of analysis_mode values whose real
    technique depends on the project's analysis_scale too (see
    _SCALE_DEPENDENT_TECHNIQUE) - e.g. national-scale Active Transport
    uses a different technique from the same analysis_mode at regional
    or local scale. Prefer this over technique_for_analysis_mode()
    wherever the project's analysis_scale is known; falls back to the
    plain analysis_mode-only lookup otherwise.

    Args:
        analysis_mode: The indicator's own analysis_mode attribute.
        analysis_scale: The project's analysis_scale ("national",
            "regional", "local"), or None if unknown.

    Returns:
        The technique key, or None if analysis_mode isn't a
        data-collection technique.
    """
    scale_overrides = _SCALE_DEPENDENT_TECHNIQUE.get(analysis_mode)
    if scale_overrides and analysis_scale in scale_overrides:
        return scale_overrides[analysis_scale]
    return technique_for_analysis_mode(analysis_mode)


def nuance_for_analysis_mode(analysis_mode: str) -> str:
    """One-sentence note on how this specific analysis_mode's data or
    scoring differs from its technique siblings, or "" if there's
    nothing beyond the technique's own general description.
    """
    return ANALYSIS_MODE_NUANCE.get(analysis_mode, "")
