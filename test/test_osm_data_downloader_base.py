# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

try:
    from defusedxml import ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET  # nosec B405

from geest.core.osm_downloaders.osm_data_downloader_base import OSMDataDownloaderBase


class TestGetEntityName(unittest.TestCase):
    def test_returns_name_tag_value(self):
        node = ET.fromstring(  # nosec B314
            '<node id="1"><tag k="amenity" v="pharmacy"/><tag k="name" v="Corner Pharmacy"/></node>'
        )
        self.assertEqual(OSMDataDownloaderBase._get_entity_name(node), "Corner Pharmacy")

    def test_falls_back_to_amenity_when_no_name_tag(self):
        node = ET.fromstring('<node id="1"><tag k="amenity" v="pharmacy"/></node>')  # nosec B314
        self.assertEqual(OSMDataDownloaderBase._get_entity_name(node), "pharmacy")

    def test_falls_back_to_shop_when_no_name_or_amenity_tag(self):
        node = ET.fromstring('<node id="1"><tag k="shop" v="bakery"/></node>')  # nosec B314
        self.assertEqual(OSMDataDownloaderBase._get_entity_name(node), "bakery")

    def test_name_tag_takes_precedence_over_amenity(self):
        node = ET.fromstring(  # nosec B314
            '<node id="1"><tag k="amenity" v="pharmacy"/><tag k="name" v="Corner Pharmacy"/></node>'
        )
        self.assertEqual(OSMDataDownloaderBase._get_entity_name(node), "Corner Pharmacy")

    def test_returns_empty_string_when_no_tags(self):
        node = ET.fromstring('<node id="1"/>')  # nosec B314
        self.assertEqual(OSMDataDownloaderBase._get_entity_name(node), "")


class TestValidateOsmXmlResponse(unittest.TestCase):
    def _downloader_with_xml(self, content: str) -> OSMDataDownloaderBase:
        downloader = OSMDataDownloaderBase.__new__(OSMDataDownloaderBase)
        fd, path = tempfile.mkstemp(suffix=".xml")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        downloader.output_xml_path = path
        return downloader

    def test_accepts_well_formed_osm_response(self):
        downloader = self._downloader_with_xml('<osm version="0.6"><node id="1" lat="0" lon="0"/></osm>')
        downloader._validate_osm_xml_response()  # should not raise

    def test_rejects_non_osm_root_element(self):
        downloader = self._downloader_with_xml("<remark>Query timed out</remark>")
        with self.assertRaisesRegex(RuntimeError, "did not return OSM data"):
            downloader._validate_osm_xml_response()

    def test_rejects_unparseable_response(self):
        downloader = self._downloader_with_xml("Rate limited, try again later")
        with self.assertRaisesRegex(RuntimeError, "did not return valid OSM data"):
            downloader._validate_osm_xml_response()


if __name__ == "__main__":
    unittest.main()
