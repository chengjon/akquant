#!/bin/bash
# Script to run tests with correct library paths for PyO3 on macOS

# Set DYLD_LIBRARY_PATH to include the Python library
# This is required because PyO3 links against libpython dynamically,
# and on macOS the dynamic linker needs to know where to find it.
export DYLD_LIBRARY_PATH=/Users/albert/miniconda3/envs/akquant/lib:$DYLD_LIBRARY_PATH

echo "Running cargo test with DYLD_LIBRARY_PATH set..."
cargo test "$@"
