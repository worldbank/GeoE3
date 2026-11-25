#!/usr/bin/env bash

qgis_setup.sh

# FIX default installation because the sources must be in "geest" parent folder
rm -rf /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geest
ln -sf /tests_directory /root/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geest
ln -sf /tests_directory /usr/share/qgis/python/plugins/geest

# test_suite.py imports coverage unconditionally and auto-installs it
# via pip if missing; test_grid_from_bbox_h3_task.py needs h3. Older
# QGIS images (3.30-3.36) ship coverage pre-installed and have no PEP
# 668 "externally managed environment" restriction, so this was never
# needed there - newer images (3.44+/4.x) ship neither package AND
# enforce PEP 668, so that auto-install silently crashed the whole test
# run with no output at all before a single test could print anything.
# --break-system-packages isn't recognised by every pip version still
# in the matrix, hence the fallback; this container is thrown away
# after the test run, so there is no real system to break.
python3 -m pip install --break-system-packages --quiet coverage h3==4.4.2 2>/dev/null \
    || python3 -m pip install --quiet coverage h3==4.4.2

# qgis_testrunner.sh (baked into the qgis/qgis image, not this repo)
# pipes its test run through `unbuffer` before `tee`-ing it to a log
# file. Older images ship `unbuffer` (from the `expect` package);
# newer ones (3.44+/4.x) don't - bash's own "unbuffer: command not
# found" on stderr there is itself swallowed by qgis_testrunner.sh's
# own `2>/dev/null`, so the pipe silently receives nothing and every
# test run reports "no output from the test runner" despite the suite
# itself running fine. Installing it here is a no-op where it's
# already present.
if ! command -v unbuffer >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y --no-install-recommends expect
fi
