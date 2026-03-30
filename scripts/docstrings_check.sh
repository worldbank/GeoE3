#!/usr/bin/env bash

# SPDX-FileCopyrightText: Tim Sutton
# SPDX-License-Identifier: MIT
#
# 🤖 Add a check that ensures that any python modules updated
# have docstrings in google docstring format for every method,
# function and class.

missing=0

# Check if darglint is available
if ! which darglint >/dev/null 2>&1; then
    echo "darglint not installed. Skipping docstring checks."
    echo "To enable docstring validation, install it with: pip install darglint"
    exit 0
fi

for file in $(git diff --cached --name-only --diff-filter=ACM | grep -E "\.py$"); do
    if ! output=$(darglint --docstring-style=google "$file" 2>&1); then
        echo "Docstring check failed for: $file"
        echo "$output"
        missing=1
    fi
done
exit $missing
