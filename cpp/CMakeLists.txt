cmake_minimum_required(VERSION 3.16)
project(metro_planner VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Static library: core logic
# ---------------------------------------------------------------------------
add_library(metro_core STATIC
    src/station.cpp
    src/graph.cpp
    src/csv.cpp
    src/utils.cpp
    src/pathfinder.cpp
    src/network_analysis.cpp
)
target_include_directories(metro_core PUBLIC include)

# ---------------------------------------------------------------------------
# Executable: interactive console app
# ---------------------------------------------------------------------------
add_executable(metro_app
    src/main.cpp
    src/menu.cpp
)
target_link_libraries(metro_app PRIVATE metro_core)

# ---------------------------------------------------------------------------
# Executable: data builder
# ---------------------------------------------------------------------------
add_executable(build_dataset
    src/build_dataset.cpp
)
target_link_libraries(build_dataset PRIVATE metro_core)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
enable_testing()
add_executable(metro_tests
    tests/test_cases.cpp
)
target_link_libraries(metro_tests PRIVATE metro_core)
target_include_directories(metro_tests PRIVATE third_party)

add_test(NAME metro_tests COMMAND metro_tests)
