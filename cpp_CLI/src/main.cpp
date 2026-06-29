// main.cpp —— 程序入口 + 控制台菜单系统。
//
// 结构：一级主菜单 + 三个二级子菜单
//   主菜单：
//     1) 线路站点信息/运营状态管理   → run_submenu_1（含 8 个功能项）
//     2) 所需时间最短路径规划       → run_submenu_2（M3）
//     3) 所需换乘次数最少路径规划   → run_submenu_3（M4）
//     4) 退出系统
//
// 鲁棒性保证：
//   ① 所有数字输入经 prompt_int 校验：非整数、浮点、范围外、负数全部拒绝
//      并循环重提示，不会让程序崩溃或脱离当前菜单层。
//   ② 任一菜单循环都以用户主动"返回上级"才退出，错误选择永远回到当前菜单。
//   ③ 所有路径规划入口前都经 pathfinder::guard 校验起终点（相同/关闭/未知）。
//   ④ 启动时切 Windows 控制台为 UTF-8 以正确渲染中文站名。

#include "csv.hpp"
#include "station.hpp"
#include "graph.hpp"
#include "pathfinder.hpp"

#include <iostream>
#include <filesystem>
#include <string>
#include <sstream>
#include <stdexcept>
#include <limits>
#include <algorithm>

#ifdef _WIN32
#include <windows.h>
#endif

namespace fs = std::filesystem;
using mini::Station;

namespace {

// ============================================================================
// 终端辅助：UTF-8 控制台、整型输入校验、Y/N 提示
// ============================================================================

void enable_utf8_console() {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif
}

// Read a trimmed line. Returns false on EOF.
bool getline_trim(std::string& out) {
    if (!std::getline(std::cin, out)) return false;
    out = mini::trim(out);
    return true;
}

// 从控制台读取一个 [lo, hi] 范围内的整数，无效输入循环重试。
// 拒绝的输入：非数字（"abc"）、浮点数（"1.5"）、范围外（含负数）。
// 仅在 stdin EOF（管道结束）时返回 -1，让上层菜单平滑退出。
int prompt_int(const std::string& prompt, int lo, int hi) {
    while (true) {
        std::cout << prompt;
        std::string s;
        if (!getline_trim(s)) return -1;
        try {
            size_t pos = 0;
            int n = std::stoi(s, &pos);
            // stoi 只解析前缀，所以必须再校验剩余位（如 "1.5" 的 .5 部分）
            if (pos != s.size()) throw std::invalid_argument("trail");
            if (n < lo || n > hi) throw std::out_of_range("range");
            return n;
        } catch (...) {
            std::cout << "输入无效，请输入数字选项 " << lo << "-" << hi << "。\n";
        }
    }
}

// Y/N 提示；输入首字符为 Y/y 视作肯定，其他一律否定（含 EOF）。
bool prompt_yn(const std::string& prompt) {
    std::cout << prompt;
    std::string s;
    if (!getline_trim(s)) return false;
    return !s.empty() && (s[0] == 'Y' || s[0] == 'y');
}

// 解析数据目录位置：优先使用 --data 指定的路径，否则按候选列表逐个尝试，
// 让用户既能从仓库根目录又能从 cpp_CLI/ 或 cpp_CLI/build/ 下启动程序。
fs::path resolve_data_dir(const std::string& override_path = "") {
    if (!override_path.empty()) {
        fs::path p = override_path;
        if (fs::exists(p / "Station.csv")) return p;
        throw std::runtime_error("指定的数据目录无效: " + override_path);
    }
    for (const char* rel : { "../python/data", "python/data",
                              "../../python/data", "data" }) {
        fs::path p = rel;
        if (fs::exists(p / "Station.csv") && fs::exists(p / "Edge.csv")) {
            return p;
        }
    }
    throw std::runtime_error(
        "未找到数据目录。请将工作目录切到 metro/ 或 cpp_CLI/ 下，"
        "或通过命令行 --data <path> 指定。");
}

// ============================================================================
// 站点模糊检索器
// ============================================================================
// Returns the chosen station's id, or "" if the user cancelled or no match.
// If `require_open` is true, closed stations are filtered out of the hit list
// before display — appropriate for path-planning prompts, which would
// otherwise present a station only to have pathfinder::guard reject it.
std::string pick_station(const std::string& prompt,
                          const mini::StationManager& m,
                          bool require_open = false) {
    std::cout << prompt;
    std::string kw;
    if (!getline_trim(kw) || kw.empty()) return "";
    auto hits = m.find_fuzzy(kw);
    if (require_open) {
        hits.erase(std::remove_if(hits.begin(), hits.end(),
                                   [](const mini::Station* s) { return !s->open(); }),
                   hits.end());
    }
    if (hits.empty()) {
        std::cout << "未找到匹配的站点,请重新选择。\n";
        return "";
    }
    if (hits.size() == 1) return hits[0]->id;
    std::cout << "找到 " << hits.size() << " 个匹配站点:\n";
    for (size_t i = 0; i < hits.size(); ++i) {
        std::cout << "  " << (i + 1) << ". " << hits[i]->name
                  << " (" << hits[i]->line << ")"
                  << (hits[i]->open() ? "" : " [关闭]") << "\n";
    }
    int idx = prompt_int("请输入编号: ", 1, static_cast<int>(hits.size()));
    if (idx < 1) return "";
    return hits[static_cast<size_t>(idx - 1)]->id;
}

// ============================================================================
// 路径结果打印辅助
// ============================================================================

void print_path(const mini::PathResult& r,
                const mini::StationManager& m,
                const mini::Graph& g) {
    std::cout << mini::pf::format(r, m, g) << "\n";
}

void print_paths(const std::vector<mini::PathResult>& v,
                  const mini::StationManager& m,
                  const mini::Graph& g) {
    if (v.empty()) {
        std::cout << "未找到可行路径。\n";
        return;
    }
    if (v.size() == 1 && !v[0].valid) {
        std::cout << mini::pf::format(v[0], m, g) << "\n";
        return;
    }
    for (size_t i = 0; i < v.size(); ++i) {
        std::cout << "\n=== 第 " << (i + 1) << " 条路径 ===\n";
        std::cout << mini::pf::format(v[i], m, g) << "\n";
    }
}

// ============================================================================
// 子菜单 1：线路 / 站点 / 运营状态管理（对应课设 M2 模块）
// ============================================================================

void submenu_csv_update(mini::StationManager& m, const fs::path& data_dir) {
    std::cout << "更新文件路径(直接回车使用默认 "
              << (data_dir / "update_station_status.csv").string() << "): ";
    std::string path;
    getline_trim(path);
    fs::path use = path.empty() ? (data_dir / "update_station_status.csv") : fs::path(path);
    if (!fs::exists(use)) { std::cout << "更新文件不存在。\n"; return; }
    try {
        auto stats = m.batch_update(use);
        m.save(data_dir / "Station.csv");
        std::cout << "批量更新完成: 修改站点 " << stats.updated
                  << " 个，未匹配 " << stats.not_found
                  << " 行，无效 " << stats.invalid << " 行。\n";
        // Print the first few per-row diagnostics — when something doesn't go
        // through, the user wants to know which rows and why. Cap to avoid
        // dumping hundreds of lines on a malformed file.
        constexpr size_t MAX_ERRORS_SHOWN = 10;
        if (!stats.errors.empty()) {
            std::cout << "诊断信息:\n";
            size_t shown = std::min(stats.errors.size(), MAX_ERRORS_SHOWN);
            for (size_t i = 0; i < shown; ++i) {
                std::cout << "  · " << stats.errors[i] << "\n";
            }
            if (stats.errors.size() > shown) {
                std::cout << "  ...（共 " << stats.errors.size()
                          << " 条，已省略 " << (stats.errors.size() - shown)
                          << " 条）\n";
            }
        }
    } catch (const std::exception& e) {
        std::cout << "更新失败: " << e.what() << "\n";
    }
}

void submenu_manual_update(mini::StationManager& m, const fs::path& data_dir) {
    std::string id = pick_station("请输入要修改的站点关键词: ", m);
    if (id.empty()) return;
    const Station* s = m.get(id);
    std::cout << "当前: " << s->name << " (" << s->line << ") 状态=" << s->status << "\n";
    std::cout << "请输入新状态 (开启/关闭): ";
    std::string st; getline_trim(st);
    if (st != "开启" && st != "关闭") { std::cout << "状态值非法。\n"; return; }
    m.set_status(id, st);
    m.save(data_dir / "Station.csv");
    std::cout << "修改站点: " << s->name << " (" << s->line << ") -> 状态: "
              << st << "。1 个站点的状态修改完成。\n";
}

void submenu_show_closed(const mini::StationManager& m) {
    auto closed = m.closed();
    if (closed.empty()) { std::cout << "所有站点均处于开放状态。\n"; return; }
    std::cout << "当前关闭站点（共 " << closed.size() << " 个）:\n";
    for (const auto* s : closed) {
        std::cout << "  · " << s->name << " (" << s->line << ")\n";
    }
}

void submenu_restore(mini::StationManager& m, const fs::path& data_dir) {
    if (!prompt_yn("您确定要恢复所有站点的初始状态?（Y/N）: ")) return;
    if (m.restore_initial(data_dir / "Station_init.csv")) {
        m.save(data_dir / "Station.csv");
        std::cout << "已恢复至初始状态。\n";
    } else {
        std::cout << "恢复失败（备份文件 Station_init.csv 缺失或损坏）。\n";
    }
}

// Map line number 1..18 + "浦江"/"机场" to canonical line label used in CSVs.
std::string line_label(int n) {
    if (n >= 1 && n <= 18) return std::to_string(n) + "号线";
    return "";
}

void submenu_show_line(const mini::StationManager& m) {
    int n = prompt_int("请输入线路编号 (1-18，输入 0 查询浦江/机场线): ", 0, 20);
    if (n < 0) return;
    std::string label;
    if (n == 0) {
        std::cout << "  1) 浦江线  2) 机场线: ";
        std::string s; getline_trim(s);
        if (s == "1") label = "浦江线";
        else if (s == "2") label = "机场线";
    } else if (n >= 1 && n <= 18) {
        label = line_label(n);
    }
    if (label.empty()) { std::cout << "线路编号无效。\n"; return; }
    auto stations = m.of_line(label);
    if (stations.empty()) { std::cout << "未找到该线路: " << label << "\n"; return; }
    std::cout << label << " 共 " << stations.size() << " 站:\n";
    for (const auto* s : stations) {
        auto xfr = m.transfers_for(s->name, s->line);
        std::cout << "  " << s->id << "  " << s->name
                  << "  [" << (s->open() ? "开启" : "关闭") << "]";
        if (!xfr.empty()) {
            std::cout << "  换乘:";
            for (const auto& l : xfr) std::cout << " " << l;
        }
        std::cout << "\n";
    }
}

void submenu_affected(const mini::StationManager& m, const mini::Graph& g) {
    std::string id = pick_station("请输入受影响分析的目标站点关键词: ", m);
    if (id.empty()) return;
    int order = prompt_int("请输入影响半径 (邻接阶数 K，1-5): ", 1, 5);
    if (order < 1) return;
    auto ids = mini::pf::affected_area(id, g, m, order);
    const Station* src = m.get(id);
    std::cout << "若 " << src->name << " (" << src->line << ") 关闭，"
              << order << " 阶邻接波及 " << ids.size() << " 个开放站点:\n";
    for (const auto& aid : ids) {
        const Station* s = m.get(aid);
        if (s) std::cout << "  · " << s->name << " (" << s->line << ")\n";
    }
}

void submenu_query(const mini::StationManager& m) {
    std::string id = pick_station("请输入站点查询关键词: ", m);
    if (id.empty()) return;
    const Station* s = m.get(id);
    auto xfr = m.transfers_for(s->name, s->line);
    std::cout << "站点ID: " << s->id << "\n站点名: " << s->name
              << "\n所属线路: " << s->line << "\n运营状态: " << s->status << "\n";
    if (!xfr.empty()) {
        std::cout << "换乘线路:";
        for (const auto& l : xfr) std::cout << " " << l;
        std::cout << "\n";
    } else {
        std::cout << "（无换乘）\n";
    }
}

void run_submenu_1(mini::StationManager& m,
                    const mini::Graph& g,
                    const fs::path& data_dir) {
    while (true) {
        std::cout << "\n-- 线路站点信息/运营状态管理 --\n"
                  << "1. 从 CSV 文件批量更新站点开启/关闭状态\n"
                  << "2. 手工更新站点开启/关闭状态\n"
                  << "3. 显示当前关闭站点\n"
                  << "4. 恢复所有站点初始状态\n"
                  << "5. 显示线路站点信息\n"
                  << "6. 受关闭站点影响站点分析\n"
                  << "7. 全网连通分量检测\n"
                  << "8. 站点查询\n"
                  << "9. 返回上级菜单\n";
        int c = prompt_int("请输入选项编号: ", 1, 9);
        if (c < 0 || c == 9) return;
        switch (c) {
            case 1: submenu_csv_update(m, data_dir); break;
            case 2: submenu_manual_update(m, data_dir); break;
            case 3: submenu_show_closed(m); break;
            case 4: submenu_restore(m, data_dir); break;
            case 5: submenu_show_line(m); break;
            case 6: submenu_affected(m, g); break;
            case 7: {
                int n = mini::pf::component_count(g, m);
                std::cout << "当前开放子图的连通分量数: " << n
                          << (n == 1 ? "（全网连通）" : "（存在断裂子网）") << "\n";
                break;
            }
            case 8: submenu_query(m); break;
        }
    }
}

// ============================================================================
// 子菜单 2 / 3：路径规划（M3 最短时间 / M4 最少换乘）
// ============================================================================

void plan(const mini::StationManager& m, const mini::Graph& g,
          bool by_time, int k) {
    // Path planning rejects closed endpoints up front — the user shouldn't be
    // offered a closed station in the picker, see it routed-around, then get a
    // rejection from pathfinder::guard. Other menus (status query, manual
    // update, affected-area) keep require_open=false because they NEED to
    // operate on closed stations.
    std::string src = pick_station("请输入起点关键词: ", m, /*require_open=*/true);
    if (src.empty()) return;
    std::string dst = pick_station("请输入终点关键词: ", m, /*require_open=*/true);
    if (dst.empty()) return;
    if (by_time) {
        if (k == 1) print_path(mini::pf::shortest_time(src, dst, g, m), m, g);
        else        print_paths(mini::pf::k_shortest_time(src, dst, g, m, k), m, g);
    } else {
        if (k == 1) print_path(mini::pf::min_transfers(src, dst, g, m), m, g);
        else        print_paths(mini::pf::k_min_transfers(src, dst, g, m, k), m, g);
    }
}

void run_submenu_2(const mini::StationManager& m, const mini::Graph& g) {
    while (true) {
        std::cout << "\n-- 所需时间最短路径规划 --\n"
                  << "1. 单条所需时间最短路径\n"
                  << "2. 3 条所需时间最短路径\n"
                  << "3. 返回上级菜单\n";
        int c = prompt_int("请输入选项编号: ", 1, 3);
        if (c < 0 || c == 3) return;
        plan(m, g, /*by_time=*/true, c == 1 ? 1 : 3);
    }
}

void run_submenu_3(const mini::StationManager& m, const mini::Graph& g) {
    while (true) {
        std::cout << "\n-- 所需换乘次数最少路径规划 --\n"
                  << "1. 单条换乘次数最少路径\n"
                  << "2. 3 条换乘次数最少路径\n"
                  << "3. 返回主菜单\n";
        int c = prompt_int("请输入选项编号: ", 1, 3);
        if (c < 0 || c == 3) return;
        plan(m, g, /*by_time=*/false, c == 1 ? 1 : 3);
    }
}

} // anonymous namespace

int main(int argc, char** argv) {
    enable_utf8_console();

    // Optional: `--data <dir>` overrides auto-detection.
    std::string data_override;
    for (int i = 1; i + 1 < argc; ++i) {
        if (std::string(argv[i]) == "--data") { data_override = argv[i + 1]; break; }
    }

    fs::path data_dir;
    mini::StationManager mgr;
    mini::Graph g;
    try {
        data_dir = resolve_data_dir(data_override);
        mgr.load(data_dir / "Station.csv");
        g.load(data_dir / "Edge.csv");
    } catch (const std::exception& e) {
        std::cerr << "[启动失败] " << e.what() << "\n";
        return 1;
    }

    std::cout << "[OK] 数据目录: " << data_dir.string() << "\n"
              << "      站点数: " << mgr.size()
              << "  图节点数: " << g.node_count()
              << "  边数: " << g.edge_count() << "\n";

    while (true) {
        std::cout << "\n==== 地铁路径规划系统 ====\n"
                  << "1. 线路站点信息/运营状态管理\n"
                  << "2. 所需时间最短路径规划\n"
                  << "3. 所需换乘次数最少路径规划\n"
                  << "4. 退出系统\n";
        int c = prompt_int("请输入选项编号: ", 1, 4);
        if (c < 0 || c == 4) {
            std::cout << "再见。\n";
            return 0;
        }
        switch (c) {
            case 1: run_submenu_1(mgr, g, data_dir); break;
            case 2: run_submenu_2(mgr, g); break;
            case 3: run_submenu_3(mgr, g); break;
        }
    }
}
