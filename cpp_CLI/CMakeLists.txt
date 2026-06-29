cmake_minimum_required(VERSION 3.15)
project(metro_cli CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/W4 /utf-8)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

add_executable(metro_cli
    src/csv.cpp
    src/station.cpp
    src/graph.cpp
    src/pathfinder.cpp
    src/main.cpp
)
target_include_directories(metro_cli PRIVATE include)

# On MinGW, statically link so the .exe is portable without DLLs on PATH.
if(MINGW)
    target_link_options(metro_cli PRIVATE -static -static-libgcc -static-libstdc++)
endif()
