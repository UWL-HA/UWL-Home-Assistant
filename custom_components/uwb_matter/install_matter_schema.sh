#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_file="$source_dir/matter_schema/ultrawidelock-cluster.mjs"
target_dir="/addon_configs/core_matter_server"
target_file="$target_dir/ultrawidelock-cluster.mjs"

if [ ! -f "$source_file" ]; then
    echo "Error: bundled UltraWideLock Matter schema not found: $source_file" >&2
    exit 1
fi
if [ ! -d "$target_dir" ]; then
    echo "Error: Matter Server app configuration directory not found: $target_dir" >&2
    exit 1
fi

cp "$source_file" "$target_file"
echo "Installed UltraWideLock Matter schema at $target_file"
echo "Restart the Matter Server app after configuring NODE_OPTIONS."
