# -*- coding: utf-8 -*-
"""Grid column utilities for model-based columns.

This module provides utilities for extracting IDs from the JSON model
and managing grid columns for indicators, factors, dimensions, and aggregate scores.
"""

import json
import os
from typing import Dict, List, Optional

from geoe3.utilities import log_message
from osgeo import ogr
from qgis.core import Qgis


def extract_model_ids(model_path: str) -> Dict[str, List[str]]:
    """Extract all IDs from the model JSON file.

    Traverses the model structure and extracts IDs for dimensions,
    factors, and indicators.

    Args:
        model_path: Path to the model.json file.

    Returns:
        Dictionary with keys 'dimensions', 'factors', 'indicators' containing
        lists of IDs for each category.
    """
    ids = {
        "dimensions": [],
        "factors": [],
        "indicators": [],
    }

    if not os.path.exists(model_path):
        log_message(f"Model file not found: {model_path}", level=Qgis.Warning)
        return ids

    try:
        with open(model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        for dimension in model.get("dimensions", []):
            dim_id = dimension.get("id", "")
            if dim_id:
                ids["dimensions"].append(dim_id.lower())

            for factor in dimension.get("factors", []):
                factor_id = factor.get("id", "")
                if factor_id:
                    ids["factors"].append(factor_id.lower())

                for indicator in factor.get("indicators", []):
                    indicator_id = indicator.get("id", "")
                    if indicator_id:
                        ids["indicators"].append(indicator_id.lower())

    except Exception as e:
        log_message(f"Error extracting model IDs: {e}", level=Qgis.Critical)

    return ids


def get_aggregate_column_names() -> List[str]:
    """Get the list of aggregate score column names.

    Returns:
        List of column names for aggregate scores (WEE score, WEE by population, etc.)
    """
    return [
        "wee_score",
        "wee_by_population",
        "contextual_score",
        "accessibility_score",
        "place_characterization_score",
    ]


def get_all_column_names(model_path: str) -> List[str]:
    """Get all column names to be added to the grid layer.

    Args:
        model_path: Path to the model.json file.

    Returns:
        List of all column names (indicators, factors, dimensions, and aggregates).
    """
    ids = extract_model_ids(model_path)
    columns = []

    # Add indicator columns
    columns.extend(ids["indicators"])

    # Add factor columns
    columns.extend(ids["factors"])

    # Add dimension columns
    columns.extend(ids["dimensions"])

    # Add aggregate columns
    columns.extend(get_aggregate_column_names())

    return columns


def add_model_columns_to_grid(gpkg_path: str, model_path: str) -> bool:
    """Add model-based columns to the study_area_grid layer.

    Adds one float column for each indicator, factor, dimension, and aggregate score
    based on the IDs from the model.json file.

    Args:
        gpkg_path: Path to the GeoPackage containing study_area_grid.
        model_path: Path to the model.json file.

    Returns:
        True if columns were added successfully, False otherwise.
    """
    column_names = get_all_column_names(model_path)

    if not column_names:
        log_message("No columns to add to grid layer", level=Qgis.Warning)
        return False

    try:
        ds = ogr.Open(gpkg_path, 1)
        if not ds:
            log_message(f"Could not open GeoPackage: {gpkg_path}", level=Qgis.Critical)
            return False

        layer = ds.GetLayerByName("study_area_grid")
        if not layer:
            log_message("study_area_grid layer not found", level=Qgis.Critical)
            ds = None
            return False

        # Get existing field names to avoid duplicates
        layer_defn = layer.GetLayerDefn()
        existing_fields = set()
        for i in range(layer_defn.GetFieldCount()):
            existing_fields.add(layer_defn.GetFieldDefn(i).GetName().lower())

        # Add new columns
        added_count = 0
        for col_name in column_names:
            # Sanitize column name (replace spaces with underscores, limit length)
            sanitized_name = col_name.replace(" ", "_").replace("-", "_")[:63]

            if sanitized_name.lower() in existing_fields:
                log_message(f"Column {sanitized_name} already exists, skipping")
                continue

            field_defn = ogr.FieldDefn(sanitized_name, ogr.OFTReal)
            if layer.CreateField(field_defn) != 0:
                log_message(f"Failed to create field: {sanitized_name}", level=Qgis.Warning)
            else:
                added_count += 1

        ds.FlushCache()
        ds = None

        log_message(f"Added {added_count} model columns to study_area_grid")
        return True

    except Exception as e:
        log_message(f"Error adding model columns to grid: {e}", level=Qgis.Critical)
        return False


def write_raster_values_to_grid(
    gpkg_path: str,
    raster_path: str,
    column_name: str,
    area_name: Optional[str] = None,
) -> int:
    """Sample raster values at grid cell centroids and write to grid column.

    Args:
        gpkg_path: Path to the GeoPackage containing study_area_grid.
        raster_path: Path to the raster file to sample.
        column_name: Name of the column to write values to.
        area_name: Optional area name to filter grid cells. If None, processes all cells.

    Returns:
        Number of cells updated, or -1 on error.
    """
    from osgeo import gdal

    if not os.path.exists(raster_path):
        log_message(f"Raster file not found: {raster_path}", level=Qgis.Warning)
        return -1

    try:
        # Open the raster
        raster_ds = gdal.Open(raster_path)
        if not raster_ds:
            log_message(f"Could not open raster: {raster_path}", level=Qgis.Critical)
            return -1

        band = raster_ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        gt = raster_ds.GetGeoTransform()

        # Open the GeoPackage for updating
        ds = ogr.Open(gpkg_path, 1)
        if not ds:
            log_message(f"Could not open GeoPackage: {gpkg_path}", level=Qgis.Critical)
            raster_ds = None
            return -1

        layer = ds.GetLayerByName("study_area_grid")
        if not layer:
            log_message("study_area_grid layer not found", level=Qgis.Critical)
            ds = None
            raster_ds = None
            return -1

        # Sanitize column name
        sanitized_column = column_name.replace(" ", "_").replace("-", "_")[:63].lower()

        # Check if column exists
        layer_defn = layer.GetLayerDefn()
        field_idx = layer_defn.GetFieldIndex(sanitized_column)
        if field_idx < 0:
            log_message(f"Column {sanitized_column} not found in grid layer", level=Qgis.Warning)
            ds = None
            raster_ds = None
            return -1

        # Set attribute filter if area_name is provided
        if area_name:
            layer.SetAttributeFilter(f"area_name = '{area_name}'")

        # Process each grid cell
        updated_count = 0
        layer.StartTransaction()

        try:
            for feature in layer:
                geom = feature.GetGeometryRef()
                if not geom:
                    continue

                # Get centroid
                centroid = geom.Centroid()
                x = centroid.GetX()
                y = centroid.GetY()

                # Convert to pixel coordinates
                px = int((x - gt[0]) / gt[1])
                py = int((y - gt[3]) / gt[5])

                # Check bounds
                if px < 0 or px >= raster_ds.RasterXSize or py < 0 or py >= raster_ds.RasterYSize:
                    continue

                # Read pixel value
                try:
                    pixel_value = band.ReadAsArray(px, py, 1, 1)
                    if pixel_value is not None:
                        value = float(pixel_value[0, 0])
                        # Skip nodata values
                        if nodata is not None and value == nodata:
                            continue
                        feature.SetField(sanitized_column, value)
                        layer.SetFeature(feature)
                        updated_count += 1
                except (RuntimeError, ValueError, IndexError):
                    # Skip cells where pixel read fails (out of bounds, invalid data)
                    continue

            layer.CommitTransaction()

        except Exception as e:
            layer.RollbackTransaction()
            log_message(f"Error writing values to grid: {e}", level=Qgis.Critical)
            ds = None
            raster_ds = None
            return -1

        # Reset filter
        layer.SetAttributeFilter(None)

        ds.FlushCache()
        ds = None
        raster_ds = None

        log_message(f"Updated {updated_count} grid cells for column {sanitized_column}")
        return updated_count

    except Exception as e:
        log_message(f"Error in write_raster_values_to_grid: {e}", level=Qgis.Critical)
        return -1
