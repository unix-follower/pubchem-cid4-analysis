#!/usr/bin/env bash

set -ex

rm -rf build

rdkit_prefix="${PUBCHEM_RDKIT_PREFIX:-${CONDA_PREFIX:-$PWD/.micromamba/rdkit}}"

if [[ -z "${PUBCHEM_RDKIT_PREFIX:-}" && -z "${CONDA_PREFIX:-}" ]]; then
	if [[ -d "$rdkit_prefix" ]]; then
		micromamba install -y -p "$rdkit_prefix" -c conda-forge librdkit-dev libboost-devel
	else
		micromamba create -y -p "$rdkit_prefix" -c conda-forge librdkit-dev libboost-devel
	fi
fi

export PUBCHEM_RDKIT_PREFIX="$rdkit_prefix"

vcpkg install
cmake --preset=vcpkg -DPUBCHEM_ENABLE_VULKAN_APP="${PUBCHEM_ENABLE_VULKAN_APP:-ON}" -DPUBCHEM_ENABLE_OPENGL_APP="${PUBCHEM_ENABLE_OPENGL_APP:-ON}" -DPUBCHEM_ENABLE_CUDA_APP="${PUBCHEM_ENABLE_CUDA_APP:-ON}"
cmake --build --preset=vcpkg
ctest --preset=vcpkg
