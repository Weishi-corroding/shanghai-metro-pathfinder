#pragma once

namespace metro {

class StationManager;
class Graph;

class ConsoleMenu {
public:
    ConsoleMenu(StationManager& mgr, Graph& graph);

    // Main entry — loops until user exits
    void main_loop();

private:
    // Top-level menu
    void show_main_menu();

    // M2: Station status management sub-menu
    void sub_menu_status();

    // M3: Shortest time path planning sub-menu
    void sub_menu_shortest_time();

    // M4: Min transfers path planning sub-menu
    void sub_menu_min_transfers();

    // --- M2 actions ---
    void batch_update();
    void manual_update();
    void show_closed();
    void restore_initial();
    void show_line_info();
    void affected_analysis();

    // --- M3/M4 actions ---
    void single_shortest_time();
    void k_shortest_time(int k);
    void single_min_transfer();
    void k_min_transfer(int k);

    StationManager& mgr_;
    Graph& graph_;
};

} // namespace metro
