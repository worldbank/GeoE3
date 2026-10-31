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
TECHNIQUES = {
    "index_score": {
        "name": "National Index Score",
        "svg": "index_score.svg",
        "description": (
            "Some of what this analysis measures doesn't change from one part of the "
            "country to another. Whether the law formally protects women from workplace "
            "discrimination, for instance, is set in national legislation — it's true "
            "(or not) everywhere at once, down to the last village. For indicators like "
            "this, every grid cell is given the same score, taken directly from a "
            "published index. A couple of the indicators that work this way are narrowed "
            "further, scored only where the underlying data actually applies — only "
            "where broadband coverage exists, say, or only inside built-up settlements. "
            "Everywhere else is left blank, rather than attaching a labour-force "
            "statistic to land where nobody lives, or an internet-use figure to a place "
            "the coverage data never reached."
        ),
    },
    "feature_count": {
        "name": "Feature Count",
        "svg": "feature_count.svg",
        "description": (
            "For some indicators, what matters is simply how much of something sits "
            "inside each cell of the grid — the number of clinics, say, or the total "
            "length of footpaths and cycle lanes running through it. This technique "
            "overlays the grid on the real-world data and tallies how many points, "
            "lines or polygons fall inside each cell. The score isn't a smooth slide "
            "from that count — a cell with nothing nearby scores 0, a cell with "
            "exactly one feature scores a middle mark, and a cell with two or more "
            "already scores the maximum. A single clinic is enough to lift a cell "
            "out of the bottom of the scale; a second one maxes it out."
        ),
    },
    "distance_buffer": {
        "name": "Straight-Line Distance",
        "svg": "distance_buffer.svg",
        "description": (
            "Other indicators are less about density and more about proximity. Can a "
            "woman reach a water point without travelling far, or has a violent "
            "incident happened nearby? This technique draws a fixed-radius circle around "
            "every relevant point, measured as the crow flies rather than along any real "
            "path, and scores a grid cell by whether it falls inside that circle or "
            "outside it. Being inside the circle is good news for a water point or a "
            "bank branch, and bad news for a reported violent event. Whether "
            "“inside” means a high score or a low one depends on what's being "
            "measured, not on the technique itself."
        ),
    },
    "network_isochrone": {
        "name": "Distance by Road",
        "svg": "network_isochrone.svg",
        "description": (
            "For indicators about reaching a service, such as a school, a hospital, or "
            "a bus stop, a straight-line circle overstates how accessible a place really "
            "is: rivers, dead-end streets and missing roads all make a destination "
            "further away in practice than it looks on a map. Rather than measuring as "
            "the crow flies, this technique traces the actual road network outward from "
            "each facility in several steps (for example a 5-, 10- and 15-minute walk) "
            "and scores a grid cell by which travel-time ring it falls inside. The "
            "resulting shape hugs the street layout rather than forming a tidy circle. "
            "For example, a facility beside the only bridge over a river reaches much "
            "further along the road than it does across the water."
        ),
    },
    "raster_lookup": {
        "name": "Map Value Lookup",
        "svg": "raster_lookup.svg",
        "description": (
            "Some of the data this analysis draws on arrives as a finished map rather "
            "than a set of points or lines — a satellite-derived picture of "
            "night-time brightness, say, or a hazard model showing flood risk across the "
            "whole country. For indicators like these, there's no counting or buffering "
            "to do: each grid cell simply reads off the value already present at that "
            "location, the same way you'd read a figure off a weather map by pointing at "
            "a city. A brightly lit area scores well on the night-time-lights indicator "
            "(used here as a rough proxy for how safe a place feels after dark); a "
            "high-risk zone scores poorly on a hazard indicator."
        ),
    },
    "zone_classification": {
        "name": "Zone Lookup",
        "svg": "zone_classification.svg",
        "description": (
            "A small number of indicators come from boundary data rather than points, "
            "lines or a continuous map — a layer of named zones, each carrying its "
            "own attribute, such as a safety rating reported by residents. This technique "
            "works out which zone a grid cell falls inside, looks up that zone's "
            "attribute value in a conversion table, and assigns the matching 0–5 "
            "score to every cell inside it. Two cells a street apart can end up with very "
            "different scores if they happen to sit on opposite sides of a zone boundary "
            "— the result is only ever as fine-grained as the zones it was collected "
            "in."
        ),
    },
    "population_share": {
        "name": "Population Share",
        "svg": "population_share.svg",
        "description": (
            "Occasionally the figure an indicator needs has already been calculated by "
            "somebody else and handed over pre-matched to this analysis's own grid — "
            "the share of a cell's population living in an urban versus a rural "
            "settlement, say, taken from aggregated census-style data. There's no "
            "spatial join or buffering left to do: the value is simply attached to the "
            "matching grid cell by a shared location key, then rescaled onto the 0–5 "
            "scale."
        ),
    },
    "weighted_feature_average": {
        "name": "Weighted Infrastructure Score",
        "svg": "weighted_feature_average.svg",
        "description": (
            "National-scale Active Transport scores a cell differently from every other "
            "indicator on this page: rather than taking the single best road or cycle "
            "path running through it, every road and cycle path intersecting the cell "
            "contributes its own score, weighted by that same score — a well-rated "
            "cycle lane counts several times more than a poorly-rated track. A cell "
            "crossed by one excellent route and nothing else no longer scores as if it "
            "were uniformly excellent, but a cell genuinely dominated by good "
            "infrastructure still scores close to the top; a cell with only poor "
            "infrastructure stays low even if a single short, better-rated segment "
            "clips its edge. Regional and local scale still use the single-best-feature "
            "technique described above."
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
