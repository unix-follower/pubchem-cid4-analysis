#!/usr/bin/env bash

set -ex

rm -rf .venv .micromamba

prefix="$PWD/.micromamba/cid4-analysis"

micromamba create -y -p "$prefix" python=3.12 --use-uv
micromamba install -y -p "$prefix" rdkit tensorflow pytorch pytorch::torchvision
uv pip install --python "$prefix/bin/python3" -e .
ln -s .micromamba/cid4-analysis .venv
