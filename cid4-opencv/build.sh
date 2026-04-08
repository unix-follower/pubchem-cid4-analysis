#!/usr/bin/env bash

set -ex

rm -rf build

vcpkg install
cmake --preset=vcpkg
cmake --build --preset=vcpkg
ctest --preset=vcpkg
