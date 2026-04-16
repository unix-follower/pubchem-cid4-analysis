#!/usr/bin/env bash

set -ex

rm -rf .venv .micromamba

prefix="$PWD/.micromamba/fastapi-app"

micromamba create -y -p "$prefix" python=3.12 --use-uv
micromamba install -y -p "$prefix" rdkit tensorflow pytorch pytorch::torchvision
uv pip install --python "$prefix/bin/python3" -e .
ln -s .micromamba/fastapi-app .venv
