// station.cpp —— 实现见 station.hpp 头文件说明。
//
// 实现要点：
//   • by_name_ / by_line_ 都是从 stations_ 派生的倒排索引；只在
//     load() / restore_initial() 这种全量替换之后调用 rebuild_indexes()
//     重建。set_status() 这类只改 status 字段的局部修改不需要重建。
//   • find_fuzzy() 先尝试整名命中（O(1) 哈希查找），找不到再退化为
//     O(N) 子串扫描——常见用法是用户输入完整站名，所以快路径覆盖了大多数。
//   • batch_update() 的"按站点计数而非按行"语义：若数据存在 (站名,线路)
//     重复（数据错误场景），一行输入实际更改了多个站点时不再被低估。
#include "station.hpp"
#include "csv.hpp"

#include <algorithm>
#include <stdexcept>
#include <iostream>

namespace mini {

void StationManager::rebuild_indexes() {
    by_name_.clear();
    by_line_.clear();
    for (const auto& [id, s] : stations_) {
        by_name_[s.name].push_back(id);
        by_line_[s.line].push_back(id);
    }
    // Sort each by id for deterministic listing order.
    for (auto& [_, v] : by_name_) std::sort(v.begin(), v.end());
    for (auto& [_, v] : by_line_) std::sort(v.begin(), v.end());
}

void StationManager::load(const std::filesystem::path& csv) {
    stations_.clear();
    auto rows = read_csv(csv);
    if (rows.empty()) throw std::runtime_error("Station.csv 为空");
    // Skip header. Expected columns: 站点ID, 站点名称, 所属线路, 运营状态
    for (size_t i = 1; i < rows.size(); ++i) {
        const auto& r = rows[i];
        if (r.size() < 4) continue;
        Station s{trim(r[0]), trim(r[1]), trim(r[2]), trim(r[3])};
        if (s.id.empty()) continue;
        if (s.status != "开启" && s.status != "关闭") s.status = "开启";
        stations_[s.id] = s;
    }
    rebuild_indexes();
}

void StationManager::save(const std::filesystem::path& csv) const {
    std::vector<std::vector<std::string>> rows;
    rows.push_back({"站点ID", "站点名称", "所属线路", "运营状态"});
    // Stable order by id.
    std::vector<std::string> ids;
    ids.reserve(stations_.size());
    for (const auto& [id, _] : stations_) ids.push_back(id);
    std::sort(ids.begin(), ids.end());
    for (const auto& id : ids) {
        const auto& s = stations_.at(id);
        rows.push_back({s.id, s.name, s.line, s.status});
    }
    write_csv(csv, rows);
}

const Station* StationManager::get(const std::string& id) const {
    auto it = stations_.find(id);
    return it == stations_.end() ? nullptr : &it->second;
}

std::vector<const Station*> StationManager::find_fuzzy(const std::string& kw) const {
    std::vector<const Station*> hits;
    if (kw.empty()) return hits;
    // 1) Exact name match (collect all line variants).
    auto it = by_name_.find(kw);
    if (it != by_name_.end()) {
        for (const auto& id : it->second) hits.push_back(&stations_.at(id));
        return hits;
    }
    // 2) Substring (byte-wise; works for UTF-8 because we never split a code point).
    for (const auto& [_, s] : stations_) {
        if (s.name.find(kw) != std::string::npos) hits.push_back(&s);
    }
    // Sort by (name, line) for stable presentation.
    std::sort(hits.begin(), hits.end(),
              [](const Station* a, const Station* b) {
                  if (a->name != b->name) return a->name < b->name;
                  return a->line < b->line;
              });
    return hits;
}

std::vector<const Station*> StationManager::of_line(const std::string& line) const {
    std::vector<const Station*> v;
    auto it = by_line_.find(line);
    if (it == by_line_.end()) return v;
    for (const auto& id : it->second) v.push_back(&stations_.at(id));
    // Order by sequence number (last 2 chars of id).
    std::sort(v.begin(), v.end(), [](const Station* a, const Station* b) {
        return a->id < b->id;
    });
    return v;
}

std::vector<const Station*> StationManager::closed() const {
    std::vector<const Station*> v;
    for (const auto& [_, s] : stations_) if (!s.open()) v.push_back(&s);
    std::sort(v.begin(), v.end(), [](const Station* a, const Station* b) {
        if (a->name != b->name) return a->name < b->name;
        return a->line < b->line;
    });
    return v;
}

std::vector<std::string> StationManager::transfers_for(
    const std::string& name, const std::string& exclude_line) const {
    std::vector<std::string> lines;
    auto it = by_name_.find(name);
    if (it == by_name_.end()) return lines;
    for (const auto& id : it->second) {
        const auto& s = stations_.at(id);
        if (s.line != exclude_line) lines.push_back(s.line);
    }
    std::sort(lines.begin(), lines.end());
    lines.erase(std::unique(lines.begin(), lines.end()), lines.end());
    return lines;
}

bool StationManager::set_status(const std::string& id, const std::string& status) {
    auto it = stations_.find(id);
    if (it == stations_.end()) return false;
    if (status != "开启" && status != "关闭") return false;
    it->second.status = status;
    return true;
}

StationManager::BatchStats StationManager::batch_update(
    const std::filesystem::path& csv) {
    BatchStats stats;
    auto rows = read_csv(csv);  // throws if file missing — caller catches
    // Expected: 站点名称, 所属线路, 运营状态. Row 1 is the header — `i` below is
    // the row index in `rows`, so the corresponding 1-based file line number is
    // `i + 1` (header is line 1, first data row is line 2).
    for (size_t i = 1; i < rows.size(); ++i) {
        const auto& r = rows[i];
        auto line_no = std::to_string(i + 1);
        if (r.size() < 3) {
            stats.errors.push_back("第 " + line_no + " 行: 字段数不足");
            ++stats.invalid;
            continue;
        }
        std::string nm = trim(r[0]), ln = trim(r[1]), st = trim(r[2]);
        if (st != "开启" && st != "关闭") {
            stats.errors.push_back("第 " + line_no + " 行: 非法状态值 '" + st + "'");
            ++stats.invalid;
            continue;
        }
        auto it = by_name_.find(nm);
        if (it == by_name_.end()) {
            stats.errors.push_back("第 " + line_no + " 行: 未匹配站点 '" + nm + "'");
            ++stats.not_found;
            continue;
        }
        // Count actually-modified station entries, not "rows that matched at
        // least once". A data error where two stations share (name, line)
        // would otherwise be silently undercounted.
        int n_matched = 0;
        for (const auto& id : it->second) {
            if (stations_[id].line == ln) {
                stations_[id].status = st;
                ++n_matched;
            }
        }
        if (n_matched > 0) {
            stats.updated += n_matched;
        } else {
            stats.errors.push_back(
                "第 " + line_no + " 行: 未匹配线路 '" + nm + " " + ln + "'");
            ++stats.not_found;
        }
    }
    return stats;
}

bool StationManager::restore_initial(const std::filesystem::path& init_csv) {
    if (!std::filesystem::exists(init_csv)) return false;
    StationManager fresh;
    try { fresh.load(init_csv); } catch (...) { return false; }
    stations_ = fresh.stations_;
    rebuild_indexes();
    return true;
}

} // namespace mini
