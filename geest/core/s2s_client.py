# -*- coding: utf-8 -*-
"""Client for querying the public Space2Stats API."""

import json
from typing import Any, Dict, List, Optional

from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtCore import QObject, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest


class S2SClient(QObject):
    """Client wrapper for Space2Stats endpoints used by GeoE3.

    This client provides thin request/response helpers for the public API.
    It intentionally keeps scope small for phase 1 integration.
    """

    VALID_JOIN_METHODS = {"touches", "centroid", "within"}
    VALID_GEOMETRIES = {"point", "polygon"}

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the S2S client.

        Args:
            base_url: API base URL. Defaults to public Space2Stats host.
        """
        super().__init__()
        self.base_url = (base_url or "https://space2stats.ds.io").rstrip("/")
        self.network_manager = QgsNetworkAccessManager.instance()

    def health(self) -> Dict[str, Any]:
        """Check API health endpoint.

        Returns:
            Parsed JSON object from the health endpoint.
        """
        result = self._request("GET", "/health")
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected /health response format.")
        return result

    def fields(self) -> List[str]:
        """Fetch available summary fields from S2S.

        Returns:
            List of field names.
        """
        result = self._request("GET", "/fields")
        if not isinstance(result, list):
            raise RuntimeError("Unexpected /fields response format.")
        return [str(value) for value in result]

    def summary(
        self,
        aoi: Dict[str, Any],
        fields: List[str],
        spatial_join_method: str = "centroid",
        geometry: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query per-hex summary records for an AOI.

        Args:
            aoi: GeoJSON feature (Polygon/MultiPolygon).
            fields: S2S field names to fetch.
            spatial_join_method: One of touches/centroid/within.
            geometry: Optional geometry type (point or polygon).

        Returns:
            List of summary rows, typically including ``hex_id`` and selected fields.
        """
        if not isinstance(aoi, dict) or not aoi:
            raise ValueError("'aoi' must be a non-empty GeoJSON feature dictionary.")

        if not isinstance(fields, list) or not fields:
            raise ValueError("'fields' must be a non-empty list of field names.")

        if spatial_join_method not in self.VALID_JOIN_METHODS:
            raise ValueError(
                f"Invalid spatial_join_method '{spatial_join_method}'. "
                f"Use one of: {sorted(self.VALID_JOIN_METHODS)}"
            )

        if geometry is not None and geometry not in self.VALID_GEOMETRIES:
            raise ValueError(f"Invalid geometry '{geometry}'. Use one of: {sorted(self.VALID_GEOMETRIES)}")

        payload: Dict[str, Any] = {
            "aoi": aoi,
            "spatial_join_method": spatial_join_method,
            "fields": fields,
        }
        if geometry is not None:
            payload["geometry"] = geometry

        result = self._request("POST", "/summary", payload)
        if not isinstance(result, list):
            raise RuntimeError("Unexpected /summary response format.")
        return result

    def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a blocking JSON request to S2S.

        Args:
            method: HTTP method (GET or POST).
            endpoint: API endpoint path.
            payload: Optional JSON payload for POST requests.

        Returns:
            Parsed JSON response payload.
        """
        url = QUrl(f"{self.base_url}{endpoint}")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        if method == "GET":
            reply = self.network_manager.blockingGet(request)
        elif method == "POST":
            data = json.dumps(payload or {}).encode("utf-8")
            reply = self.network_manager.blockingPost(request, data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status_code is None:
            raise RuntimeError("No HTTP status code received from S2S API.")

        response_text = self._extract_text(reply.content())

        if status_code == 422:
            raise ValueError(f"S2S request validation failed (422): {response_text}")
        if status_code == 429:
            raise RuntimeError("S2S API rate limit exceeded (429). Please retry later.")
        if status_code >= 500:
            raise RuntimeError(f"S2S server error ({status_code}).")
        if status_code >= 400:
            raise RuntimeError(f"S2S request failed ({status_code}): {response_text}")

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Failed to parse S2S JSON response: {error}") from error

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Convert network reply content to UTF-8 text."""
        if isinstance(content, (bytes, bytearray)):
            return bytes(content).decode("utf-8")

        if hasattr(content, "data"):
            return bytes(content).decode("utf-8")

        return str(content)
