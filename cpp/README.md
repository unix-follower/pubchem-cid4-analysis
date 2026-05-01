## Prerequisites:
- brew install cmake
```bash
which cmake
# /usr/local/bin/cmake
cmake --version
# cmake version 4.3.2
```
- brew install ninja
```bash
which ninja
# /usr/local/bin/ninja
ninja --version
# 1.13.2
```
- install vcpkg https://learn.microsoft.com/en-gb/vcpkg/get_started/get-started?pivots=shell-bash
```bash
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg && ./bootstrap-vcpkg.sh -disableMetrics
# export VCPKG_ROOT=$HOME/vcpkg
# export PATH=$VCPKG_ROOT:$PATH
# Add variables to .bash_profile
which vcpkg
# $HOME/vcpkg/vcpkg
vcpkg --version
# vcpkg package management program version 2026-04-08-e0612b42ce44e55a0e630f2ee9d3c533a63d8bc1
```
- brew install micromamba
```bash
which micromamba
# /usr/local/bin/micromamba
micromamba --version
# 2.5.0
```
- brew install llvm
- brew install clang-format@18
```bash
which clang-format
# /usr/local/opt/llvm@18/bin/clang-format
clang-format --version
# Homebrew clang-format version 18.1.8
```
