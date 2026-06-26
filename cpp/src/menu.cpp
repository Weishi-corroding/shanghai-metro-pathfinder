#include "metro/menu.hpp"
#include "metro/station.hpp"
#include "metro/graph.hpp"
#include "metro/pathfinder.hpp"
#include "metro/network_analysis.hpp"
#include "metro/utils.hpp"

#include <iostream>
#include <algorithm>

namespace metro {

// Line number to Chinese name mapping
static const std::unordered_map<int, std::string> LINE_NUMBERS = {
    {1, "1号线"}, {2, "2号线"}, {3, "3号线"}, {4, "4号线"},
    {5, "5号线"}, {6, "6号线"}, {7, "7号线"}, {8, "8号线"},
    {9, "9号线"}, {10, "10号线"}, {11, "11号线"}, {12, "12号线"},
    {13, "13号线"}, {14, "14号线"}, {15, "15号线"}, {16, "16号线"},
    {17, "17号线"}, {18, "18号线"}, {41, "浦江线"}, {51, "市域机场线"},
};

ConsoleMenu::ConsoleMenu(StationManager& mgr, Graph& graph)
    : mgr_(mgr), graph_(graph) {}

// =========================================================================
// Main menu
// =========================================================================

void ConsoleMenu::main_loop() {
    while (true) {
        std::cout << "\n";
        std::cout << "==============================================\n";
        std::cout << "  上海地铁路径规划与运营管理系统\n";
        std::cout << "==============================================\n";
        std::cout << "1. 线路站点信息/运营状态管理\n";
        std::cout << "2. 所需时间最短路径规划\n";
        std::cout << "3. 所需换乘次数最少路径规划\n";
        std::cout << "4. 退出系统\n";

        int choice = utils::read_menu_choice("请输入选项编号: ", 1, 4);

        switch (choice) {
            case 1: sub_menu_status(); break;
            case 2: sub_menu_shortest_time(); break;
            case 3: sub_menu_min_transfers(); break;
            case 4:
                std::cout << "感谢使用！再见！\n";
                return;
        }
    }
}

// =========================================================================
// Sub-menu 1: Station status management
// =========================================================================

void ConsoleMenu::sub_menu_status() {
    while (true) {
        std::cout << "\n";
        std::cout << "-- 线路站点信息/运营状态管理 --\n";
        std::cout << "1. 从 CSV 文件批量更新站点开启/关闭状态\n";
        std::cout << "2. 手工更新站点开启/关闭状态\n";
        std::cout << "3. 显示当前关闭站点\n";
        std::cout << "4. 恢复所有站点初始状态\n";
        std::cout << "5. 显示线路站点信息\n";
        std::cout << "6. 受关闭站点影响分析\n";
        std::cout << "7. 返回上级菜单\n";

        int choice = utils::read_menu_choice("请输入选项编号: ", 1, 7);

        switch (choice) {
            case 1: batch_update(); break;
            case 2: manual_update(); break;
            case 3: show_closed(); break;
            case 4: restore_initial(); break;
            case 5: show_line_info(); break;
            case 6: affected_analysis(); break;
            case 7: return;
        }
    }
}

void ConsoleMenu::batch_update() {
    namespace fs = std::filesystem;
    fs::path path = fs::path("data") / "update_station_status.csv";

    if (!fs::exists(path)) {
        std::cout << "更新文件不存在: " << path.string() << "\n";
        return;
    }

    auto stats = mgr_.batch_update_from_csv(path);

    if (!stats.errors.empty()) {
        for (const auto& e : stats.errors) {
            std::cout << "  " << e << "\n";
        }
        // If there were only errors and no updates, return early
        if (stats.updated == 0) return;
    }

    std::cout << "批量更新完成:\n";
    std::cout << "  更新: " << stats.updated << " 条\n";
    if (stats.not_found) {
        std::cout << "  未匹配: " << stats.not_found << " 条\n";
    }
    if (stats.invalid) {
        std::cout << "  非法状态: " << stats.invalid << " 条\n";
    }
    mgr_.save(std::filesystem::path("data") / "Station.csv");
}

void ConsoleMenu::manual_update() {
    int updated = 0;

    auto all = mgr_.all_stations();
    // Filter: all stations are modifiable (line != "换乘" is a no-op in our data)
    std::vector<const Station*> modifiable;
    for (auto s : all) {
        if (s->line != "换乘") {
            modifiable.push_back(s);
        }
    }

    if (modifiable.empty()) {
        std::cout << "当前无可操作站点。\n";
        return;
    }

    std::cout << "请输入待修改站点关键词（exit 退出）：\n";
    while (true) {
        std::cout << "> " << std::flush;
        std::string keyword;
        if (!std::getline(std::cin, keyword)) break;
        // Trim
        keyword.erase(0, keyword.find_first_not_of(" \t\r\n"));
        keyword.erase(keyword.find_last_not_of(" \t\r\n") + 1);

        if (keyword == "exit" || keyword == "quit" || keyword == "q") break;
        if (keyword.empty()) continue;

        auto candidates = mgr_.find_fuzzy(keyword);
        if (candidates.empty()) {
            auto exact = mgr_.find_by_name(keyword);
            candidates = std::move(exact);
        }

        // Filter to modifiable stations
        std::vector<const Station*> filtered;
        for (auto c : candidates) {
            for (auto ms : modifiable) {
                if (c->id == ms->id) {
                    filtered.push_back(c);
                    break;
                }
            }
        }

        if (filtered.empty()) {
            std::cout << "未匹配到对应站点，请重新输入。\n";
            continue;
        }

        const Station* sel = nullptr;
        if (filtered.size() == 1) {
            sel = filtered[0];
        } else {
            std::cout << "匹配的站点如下：\n";
            for (size_t i = 0; i < filtered.size(); ++i) {
                std::cout << "  " << (i + 1) << ". " << filtered[i]->name
                          << "（" << filtered[i]->line << "）\n";
            }
            std::cout << "请输入对应编号选择站点: " << std::flush;
            std::string idx_str;
            std::getline(std::cin, idx_str);
            try {
                int idx = std::stoi(idx_str);
                if (idx < 1 || idx > static_cast<int>(filtered.size())) {
                    std::cout << "编号无效。\n";
                    continue;
                }
                sel = filtered[static_cast<size_t>(idx - 1)];
            } catch (...) {
                std::cout << "输入无效。\n";
                continue;
            }
        }

        std::cout << sel->name << "," << sel->line << "," << sel->status << "\n";
        std::cout << "请输入站点状态（开启/关闭）: " << std::flush;
        std::string new_status;
        std::getline(std::cin, new_status);
        // Trim
        new_status.erase(0, new_status.find_first_not_of(" \t\r\n"));
        new_status.erase(new_status.find_last_not_of(" \t\r\n") + 1);

        if (new_status != "开启" && new_status != "关闭") {
            std::cout << "状态值非法，必须为\"开启\"或\"关闭\"\n";
            continue;
        }

        mgr_.set_status(sel->id, new_status);
        ++updated;
        std::cout << "修改站点: " << sel->name << "(" << sel->line
                  << ") -> 状态: " << new_status << "\n";
    }

    std::cout << updated << " 个站点的状态修改完成。\n";
    mgr_.save(std::filesystem::path("data") / "Station.csv");
}

void ConsoleMenu::show_closed() {
    auto closed = mgr_.closed_stations();
    if (closed.empty()) {
        std::cout << "所有站点均处于开放状态。\n";
        return;
    }

    std::cout << "当前关闭站点（共 " << closed.size() << " 个）：\n";
    for (auto s : closed) {
        std::cout << "  . " << s->name << "（" << s->line << "）\n";
    }
}

void ConsoleMenu::restore_initial() {
    if (!utils::read_yes_no("您确定要恢复所有站点的初始状态? (Y/N): ")) {
        std::cout << "已取消恢复。\n";
        return;
    }

    if (mgr_.restore_initial(std::filesystem::path("data") / "Station_init.csv")) {
        mgr_.save(std::filesystem::path("data") / "Station.csv");
        std::cout << "已成功恢复 " << mgr_.size() << " 个站点至初始状态。\n";
    } else {
        std::cout << "无法打开初始化文件或无法写入目标文件。\n";
    }
}

void ConsoleMenu::show_line_info() {
    std::cout << "请输入线路编号（1-18, 41, 51）: " << std::flush;
    std::string line_str;
    std::getline(std::cin, line_str);
    int ln;
    try {
        ln = std::stoi(line_str);
    } catch (...) {
        std::cout << "线路编号无效。\n";
        return;
    }

    auto it = LINE_NUMBERS.find(ln);
    if (it == LINE_NUMBERS.end()) {
        std::cout << "线路编号无效。\n";
        return;
    }

    const auto& line_name = it->second;
    auto stations = mgr_.stations_of_line(line_name);
    if (stations.empty()) {
        std::cout << "未找到 " << line_name << " 的站点信息。\n";
        return;
    }

    std::cout << "\n" << line_name << "（共 " << stations.size() << " 站）：\n";
    for (size_t i = 0; i < stations.size(); ++i) {
        auto s = stations[i];
        auto transfer_lines = mgr_.transfer_lines_for(s->name, s->line);

        std::string transfer_str;
        if (!transfer_lines.empty()) {
            transfer_str = "  [换乘: ";
            for (size_t j = 0; j < transfer_lines.size(); ++j) {
                if (j > 0) transfer_str += ", ";
                transfer_str += transfer_lines[j];
            }
            transfer_str += "]";
        }

        std::string closed_str = s->is_open() ? "" : " [关闭]";
        std::cout << "  " << (i + 1) << ". " << s->name
                  << transfer_str << closed_str << "\n";
    }
}

void ConsoleMenu::affected_analysis() {
    auto closed = mgr_.closed_stations();
    if (closed.empty()) {
        std::cout << "当前无关闭站点，无需分析。\n";
        return;
    }

    std::cout << "当前有 " << closed.size() << " 个关闭站点。\n";
    for (auto cs : closed) {
        auto affected_ids = analysis::affected_area(graph_, mgr_, cs->id);
        if (affected_ids.empty()) continue;

        std::vector<std::string> names;
        for (const auto& aid : affected_ids) {
            auto s = mgr_.get(aid);
            if (s) {
                names.push_back(s->name + "(" + s->line + ")");
            }
        }

        if (!names.empty()) {
            std::cout << "  " << cs->name << "(" << cs->line
                      << ") 关闭，直接影响: ";
            size_t show = std::min(names.size(), size_t(6));
            for (size_t i = 0; i < show; ++i) {
                if (i > 0) std::cout << ", ";
                std::cout << names[i];
            }
            if (names.size() > 6) {
                std::cout << "\n    ... 及其他 " << (names.size() - 6) << " 个站点";
            }
            std::cout << "\n";
        }
    }
}

// =========================================================================
// Sub-menu 2: Shortest time
// =========================================================================

void ConsoleMenu::sub_menu_shortest_time() {
    while (true) {
        std::cout << "\n";
        std::cout << "-- 所需时间最短路径规划 --\n";
        std::cout << "1. 单条所需时间最短路径\n";
        std::cout << "2. 3条所需时间最短路径\n";
        std::cout << "3. 返回上级菜单\n";

        int choice = utils::read_menu_choice("请输入选项编号: ", 1, 3);

        switch (choice) {
            case 1: single_shortest_time(); break;
            case 2: k_shortest_time(3); break;
            case 3: return;
        }
    }
}

void ConsoleMenu::single_shortest_time() {
    auto [src_id, dst_id] = utils::read_start_end_station(mgr_, "单条所需时间最短路径");
    if (src_id.empty() || dst_id.empty()) return;

    auto result = pathfinder::dijkstra_shortest_time(src_id, dst_id, graph_, mgr_);
    utils::print_path_header("最短时间路径结果");
    std::cout << pathfinder::format_path(result, mgr_, &graph_) << "\n";
}

void ConsoleMenu::k_shortest_time(int k) {
    auto [src_id, dst_id] = utils::read_start_end_station(
        mgr_, std::to_string(k) + "条所需时间最短路径");
    if (src_id.empty() || dst_id.empty()) return;

    auto results = pathfinder::yen_k_shortest_time(src_id, dst_id, graph_, mgr_, k);
    for (size_t i = 0; i < results.size(); ++i) {
        utils::print_path_header("第 " + std::to_string(i + 1) + " 条最短时间路径");
        std::cout << pathfinder::format_path(results[i], mgr_, &graph_) << "\n";
    }
}

// =========================================================================
// Sub-menu 3: Min transfers
// =========================================================================

void ConsoleMenu::sub_menu_min_transfers() {
    while (true) {
        std::cout << "\n";
        std::cout << "-- 所需换乘次数最少路径规划 --\n";
        std::cout << "1. 单条换乘次数最少路径\n";
        std::cout << "2. 3条换乘次数最少路径\n";
        std::cout << "3. 返回上级菜单\n";

        int choice = utils::read_menu_choice("请输入选项编号: ", 1, 3);

        switch (choice) {
            case 1: single_min_transfer(); break;
            case 2: k_min_transfer(3); break;
            case 3: return;
        }
    }
}

void ConsoleMenu::single_min_transfer() {
    auto [src_id, dst_id] = utils::read_start_end_station(mgr_, "单条换乘次数最少路径");
    if (src_id.empty() || dst_id.empty()) return;

    auto result = pathfinder::dijkstra_min_transfers(src_id, dst_id, graph_, mgr_);
    utils::print_path_header("最少换乘路径结果");
    std::cout << pathfinder::format_path(result, mgr_, &graph_) << "\n";
}

void ConsoleMenu::k_min_transfer(int k) {
    auto [src_id, dst_id] = utils::read_start_end_station(
        mgr_, std::to_string(k) + "条换乘次数最少路径");
    if (src_id.empty() || dst_id.empty()) return;

    auto results = pathfinder::yen_k_min_transfers(src_id, dst_id, graph_, mgr_, k);
    for (size_t i = 0; i < results.size(); ++i) {
        utils::print_path_header("第 " + std::to_string(i + 1) + " 条最少换乘路径");
        std::cout << pathfinder::format_path(results[i], mgr_, &graph_) << "\n";
    }
}

} // namespace metro
