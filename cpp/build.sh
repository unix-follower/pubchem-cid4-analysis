#!/usr/bin/env bash

set -ex

rm -rf build

vcpkg install
# cmake --list-presets
cmake --preset=default
cmake --build build
ctest --test-dir build --output-on-failure
