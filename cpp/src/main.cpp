#include "metro/station.hpp"
#include "metro/graph.hpp"
#include "metro/menu.hpp"

#include <iostream>
#include <filesystem>
#include <stdexcept>

#ifdef _WIN32
#include <windows.h>
#endif

static void enable_utf8_console() {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif
}

static std::filesystem::path find_data_dir() {
    namespace fs = std::filesystem;

    // The canonical dataset lives under python/data/
    if (fs::exists("../python/data/Edge.csv")) {
        return "../python/data";
    }
    if (fs::exists("python/data/Edge.csv")) {
        return "python/data";
    }
    if (fs::exists("data/Edge.csv")) {
        return "data";
    }
    if (fs::exists("../data/Edge.csv")) {
        return "../data";
    }

    throw std::runtime_error(
        "Cannot find data directory with Edge.csv. "
        "Please run from the repository root or cpp/ directory.");
}

int main() {
    enable_utf8_console();

    try {
        auto data_dir = find_data_dir();

        std::cout << "Loading data...\n";

        metro::Graph graph;
        graph.load(data_dir / "Edge.csv");

        metro::StationManager mgr;
        mgr.load(data_dir / "Station.csv");

        std::cout << "  Graph: " << graph.node_count() << " nodes, "
                  << graph.edge_count() << " edges\n";
        std::cout << "  Stations: " << mgr.size() << "\n";

        metro::ConsoleMenu menu(mgr, graph);
        menu.main_loop();

    } catch (const std::exception& e) {
        std::cerr << "[FATAL] " << e.what() << "\n";
        return 1;
    }

    return 0;
}
