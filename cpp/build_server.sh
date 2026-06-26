#!/bin/bash
# Build metro_server — compile and link (static for portability)
set -e
cd "$(dirname "$0")"

echo "=== Compiling server.cpp ==="
g++ -std=c++17 -Wall -static \
    -I include \
    -I third_party/cpp-httplib \
    -I third_party/nlohmann \
    -c backend/server.cpp \
    -o build/server.o

echo "=== Linking metro_server.exe (static) ==="
g++ -std=c++17 -static \
    build/station.o \
    build/graph.o \
    build/csv.o \
    build/utils.o \
    build/pathfinder.o \
    build/network_analysis.o \
    build/server.o \
    -o build/metro_server.exe \
    -lws2_32

echo "=== Done: build/metro_server.exe ==="
echo ""
echo "Usage:"
echo "  ./build/metro_server.exe --data ../python/data --port 8080"
echo "  Then open http://localhost:8080 in your browser"
