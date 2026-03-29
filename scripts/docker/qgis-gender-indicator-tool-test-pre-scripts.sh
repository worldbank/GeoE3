#!/usr/bin/env bash

qgis_setup.sh

# FIX default installation because the sources must be in "geoe3" parent folder
rm -rf /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geoe3
ln -sf /tests_directory /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geoe3
ln -sf /tests_directory /usr/share/qgis/python/plugins/geoe3
