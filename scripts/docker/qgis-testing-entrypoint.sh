#!/usr/bin/env bash

# Docker entrypoint file intended for docker-compose recipe for running unittests

set -e

# shellcheck disable=SC1091
source /tests_directory/scripts/docker/qgis-gender-indicator-tool-test-pre-scripts.sh

# Run supervisor - this is the default command of qgis/qgis but we
# will run it in background. Only on images that still ship this
# config: newer qgis/qgis images (3.44+/4.x) dropped supervisord and
# its Xvfb setup entirely, which otherwise left no display on :99 -
# qgis_testrunner.sh's GUI-mode `qgis` invocation couldn't connect,
# crashed before printing anything, and `docker compose exec` never
# saw an error (qgis_testrunner.sh redirects stderr to /dev/null).
# Xvfb itself (unlike supervisord's config) is present on every image
# in the test matrix, so starting it directly is the portable fallback.
if [ -f /etc/supervisor/supervisord.conf ]; then
    supervisord -c /etc/supervisor/supervisord.conf &
else
    Xvfb :99 -screen 0 1920x1080x24 &
fi

# Wait for XVFB
sleep 10

exec "$@"
