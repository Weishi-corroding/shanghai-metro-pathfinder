#!/usr/bin/env bash
# build.sh — single-command build using g++ directly (no CMake needed).
# Usage: ./build.sh   then   ./build/metro_cli
set -e
cd "$(dirname "$0")"
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wextra -I include \
    -static -static-libgcc -static-libstdc++ \
    src/csv.cpp src/station.cpp src/graph.cpp src/pathfinder.cpp src/main.cpp \
    -o build/metro_cli.exe
echo "[OK] build/metro_cli.exe"
