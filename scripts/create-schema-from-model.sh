#!/usr/bin/env bash

echo "Creating geoe3/resources/schema.json based on the structure of geoe3/resources/model.json"

geoe3/core/generate_schema.py
