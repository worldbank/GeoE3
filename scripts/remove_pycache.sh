#!/usr/bin/env bash
# This script recursively removes all __pycache__ directories in the 'geoe3' folder.

TARGET_DIR="geoe3"

# Check if the target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' does not exist."
    exit 1
fi

echo "Searching for __pycache__ directories in '$TARGET_DIR'..."

# Find and remove all __pycache__ directories
find "$TARGET_DIR" -type d -name "__pycache__" -exec rm -rf {} +

echo "All __pycache__ directories have been removed from '$TARGET_DIR'."
