#include "metro/utils.hpp"
#include "metro/station.hpp"

#include <iostream>
#include <string>
#include <algorithm>
#include <cctype>

namespace metro::utils {

// ---------------------------------------------------------------------------
// read_menu_choice
// ---------------------------------------------------------------------------

int read_menu_choice(const std::string& prompt, int min_val, int max_val) {
    while (true) {
        std::cout << prompt;
        std::cout.flush();

        std::string line;
        if (!std::getline(std::cin, line)) {
            // EOF — exit gracefully
            std::cout << "\n";
            return max_val;  // default to last option (usually "exit")
        }

        // Trim whitespace
        line.erase(0, line.find_first_not_of(" \t\r\n"));
        line.erase(line.find_last_not_of(" \t\r\n") + 1);

        if (line.empty()) continue;

        // Check if it's a valid integer
        bool is_int = true;
        for (char c : line) {
            if (!std::isdigit(static_cast<unsigned char>(c)) && c != '-') {
                is_int = false;
                break;
            }
        }
        if (!is_int) {
            std::cout << "[错误] 请输入数字\n";
            continue;
        }

        try {
            int val = std::stoi(line);
            if (val < min_val || val > max_val) {
                std::cout << "[错误] 请输入 " << min_val << "-" << max_val
                          << " 之间的数字\n";
                continue;
            }
            return val;
        } catch (...) {
            std::cout << "[错误] 数字格式无效\n";
        }
    }
}

// ---------------------------------------------------------------------------
// read_yes_no
// ---------------------------------------------------------------------------

bool read_yes_no(const std::string& prompt) {
    while (true) {
        std::cout << prompt;
        std::cout.flush();

        std::string line;
        if (!std::getline(std::cin, line)) {
            std::cout << "\n";
            return false;
        }

        // Trim
        line.erase(0, line.find_first_not_of(" \t\r\n"));
        line.erase(line.find_last_not_of(" \t\r\n") + 1);

        if (line.empty()) continue;

        char c = static_cast<char>(std::toupper(static_cast<unsigned char>(line[0])));
        if (c == 'Y') return true;
        if (c == 'N') return false;

        std::cout << "[错误] 请输入 Y 或 N\n";
    }
}

// ---------------------------------------------------------------------------
// fuzzy_select_station
// ---------------------------------------------------------------------------

std::string fuzzy_select_station(const StationManager& mgr,
                                  const std::string& keyword,
                                  const std::string& prompt_text) {
    std::string kw = keyword;
    while (true) {
        if (kw.empty()) {
            std::cout << prompt_text;
            std::cout.flush();
            if (!std::getline(std::cin, kw)) {
                return "";
            }
            // Trim
            kw.erase(0, kw.find_first_not_of(" \t\r\n"));
            kw.erase(kw.find_last_not_of(" \t\r\n") + 1);
        }

        if (kw.empty()) continue;

        // Exact match first
        auto exact = mgr.find_by_name(kw);
        if (exact.size() == 1) {
            return exact[0]->id;
        }

        // Fuzzy match
        auto candidates = mgr.find_fuzzy(kw);

        if (candidates.empty()) {
            std::cout << "[提示] 未找到匹配 '" << kw << "' 的站点，请重新输入\n";
            kw.clear();
            continue;
        }

        if (candidates.size() == 1) {
            // Deduplicate by name
            std::cout << "  选中: " << candidates[0]->name
                      << " (" << candidates[0]->line << ")\n";
            return candidates[0]->id;
        }

        // Multiple candidates — show numbered list, deduplicated by station id
        std::cout << "  找到 " << candidates.size() << " 个匹配站点:\n";
        for (size_t i = 0; i < candidates.size(); ++i) {
            std::cout << "    " << (i + 1) << ". " << candidates[i]->name
                      << " (" << candidates[i]->line << ")";
            if (!candidates[i]->is_open()) {
                std::cout << " [关闭]";
            }
            std::cout << "\n";
        }

        int choice = read_menu_choice(
            "  请选择 (1-" + std::to_string(candidates.size()) + ", 0=重新搜索): ",
            0, static_cast<int>(candidates.size()));

        if (choice == 0) {
            kw.clear();
            continue;
        }

        return candidates[static_cast<size_t>(choice - 1)]->id;
    }
}

// ---------------------------------------------------------------------------
// read_start_end_station
// ---------------------------------------------------------------------------

std::pair<std::string, std::string>
read_start_end_station(const StationManager& mgr, const std::string& mode_name) {
    std::cout << "\n  === " << mode_name << " ===\n";

    std::string src_id = fuzzy_select_station(mgr, "", "  请输入起点站关键词: ");
    if (src_id.empty()) return {"", ""};

    std::string dst_id = fuzzy_select_station(mgr, "", "  请输入终点站关键词: ");
    if (dst_id.empty()) return {"", ""};

    return {src_id, dst_id};
}

// ---------------------------------------------------------------------------
// print_path_header
// ---------------------------------------------------------------------------

void print_path_header(const std::string& title) {
    std::cout << "\n";
    std::cout << std::string(56, '=') << "\n";
    std::cout << "  " << title << "\n";
    std::cout << std::string(56, '=') << "\n";
}

} // namespace metro::utils
