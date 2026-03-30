#!/usr/bin/env bash
echo "🪛 Running QGIS with the GEOE3 profile:"
echo "--------------------------------"

# Set environment variables (both GEOE3_* and GEEST_* for backward compatibility)
GEOE3_TEST_DIR="$(pwd)/test"
GEEST_TEST_DIR="$(pwd)/test" # Set test directory relative to project root

# This is the flake approach, using Ivan Mincis nix spatial project and a flake
# see flake.nix for implementation details
# QT_QPA_PLATFORM flag forces it to run under x11 protocol
GEOE3_LOG=${GEOE3_LOG} \
  GEEST_LOG=${GEEST_LOG} \
  GEOE3_TEST_DIR=${GEOE3_TEST_DIR} \
  GEEST_TEST_DIR=${GEEST_TEST_DIR} \
  RUNNING_ON_LOCAL=1 \
  QT_QPA_PLATFORM=xcb \
  nix run .#qgis-ltr -- --profile GEOE3
