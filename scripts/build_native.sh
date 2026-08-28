#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_file="$project_dir/native/zip_password.cpp"
output_file="$project_dir/native/zip_password"

if command -v clang++ >/dev/null 2>&1; then
    compiler=clang++
elif command -v c++ >/dev/null 2>&1; then
    compiler=c++
else
    echo "A C++17 compiler is required" >&2
    exit 1
fi

"$compiler" -O3 -DNDEBUG -std=c++17 "$source_file" -o "$output_file" -lz
echo "Built native ZIP password helper: $output_file"
