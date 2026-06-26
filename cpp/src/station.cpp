#include "metro/station.hpp"
#include "metro/csv.hpp"

#include <algorithm>
#include <stdexcept>
#include <iostream>

namespace metro {

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

namespace {

constexpr const char* STATUS_OPEN   = "开启";
constexpr const char* STATUS_CLOSED = "关闭";

bool is_valid_status(const std::string& s) {
    return s == STATUS_OPEN || s == STATUS_CLOSED;
}

} // anonymous namespace

// ---------------------------------------------------------------------------
// Load / Save
// ---------------------------------------------------------------------------

void StationManager::load(const std::filesystem::path& csv_path) {
    csv::Reader reader(csv_path);

    stations_.clear();
    for (auto& row : reader.read_all()) {
        Station s;
        s.id     = row["站点ID"];
        s.name   = row["站点名称"];
        s.line   = row["所属线路"];
        s.status = row["运营状态"];
        stations_[s.id] = std::move(s);
    }

    rebuild_indexes();
}

void StationManager::save(const std::filesystem::path& csv_path) const {
    csv::Writer writer(csv_path, true);
    writer.write_header({"站点ID", "站点名称", "所属线路", "运营状态"});

    for (const auto& [id, s] : stations_) {
        writer.write_row({s.id, s.name, s.line, s.status});
    }
}

void StationManager::rebuild_indexes() {
    name_index_.clear();
    line_index_.clear();

    for (const auto& [id, s] : stations_) {
        name_index_[s.name].push_back(id);
        line_index_[s.line].push_back(id);
    }
}

// ---------------------------------------------------------------------------
// Query
// ---------------------------------------------------------------------------

const Station* StationManager::get(const std::string& id) const {
    auto it = stations_.find(id);
    return (it != stations_.end()) ? &it->second : nullptr;
}

std::vector<const Station*> StationManager::all_stations() const {
    std::vector<const Station*> result;
    result.reserve(stations_.size());
    for (const auto& [id, s] : stations_) {
        result.push_back(&s);
    }
    return result;
}

std::vector<const Station*> StationManager::find_by_name(const std::string& name) const {
    std::vector<const Station*> result;
    auto it = name_index_.find(name);
    if (it != name_index_.end()) {
        for (const auto& id : it->second) {
            auto sit = stations_.find(id);
            if (sit != stations_.end()) {
                result.push_back(&sit->second);
            }
        }
    }
    return result;
}

std::vector<const Station*> StationManager::find_fuzzy(const std::string& keyword) const {
    std::vector<const Station*> result;
    for (const auto& [id, s] : stations_) {
        if (s.name.find(keyword) != std::string::npos) {
            result.push_back(&s);
        }
    }
    return result;
}

std::vector<const Station*> StationManager::stations_of_line(const std::string& line) const {
    std::vector<const Station*> result;
    auto it = line_index_.find(line);
    if (it != line_index_.end()) {
        result.reserve(it->second.size());
        for (const auto& id : it->second) {
            auto sit = stations_.find(id);
            if (sit != stations_.end()) {
                result.push_back(&sit->second);
            }
        }
    }
    // Sort by station ID for consistent line ordering
    std::sort(result.begin(), result.end(),
              [](const Station* a, const Station* b) { return a->id < b->id; });
    return result;
}

std::vector<const Station*> StationManager::closed_stations() const {
    std::vector<const Station*> result;
    for (const auto& [id, s] : stations_) {
        if (!s.is_open()) {
            result.push_back(&s);
        }
    }
    return result;
}

std::vector<std::string> StationManager::transfer_lines_for(
    const std::string& station_name,
    const std::string& exclude_line) const
{
    std::vector<std::string> result;
    auto it = name_index_.find(station_name);
    if (it == name_index_.end()) return result;

    for (const auto& id : it->second) {
        auto sit = stations_.find(id);
        if (sit != stations_.end() && sit->second.line != exclude_line) {
            // Avoid duplicates (multiple stations on same line at same name)
            if (std::find(result.begin(), result.end(), sit->second.line) == result.end()) {
                result.push_back(sit->second.line);
            }
        }
    }
    return result;
}

// ---------------------------------------------------------------------------
// Status modification
// ---------------------------------------------------------------------------

bool StationManager::set_status(const std::string& id, const std::string& status) {
    if (!is_valid_status(status)) return false;

    auto it = stations_.find(id);
    if (it == stations_.end()) return false;

    it->second.status = status;
    return true;
}

bool StationManager::close_station(const std::string& id) {
    return set_status(id, STATUS_CLOSED);
}

bool StationManager::open_station(const std::string& id) {
    return set_status(id, STATUS_OPEN);
}

// ---------------------------------------------------------------------------
// Batch update
// ---------------------------------------------------------------------------

StationManager::BatchStats StationManager::batch_update_from_csv(
    const std::filesystem::path& update_csv)
{
    BatchStats stats;
    csv::Reader reader(update_csv);

    for (auto& row : reader.read_all()) {
        const auto& name = row["站点名称"];
        const auto& line = row["所属线路"];
        const auto& status = row["运营状态"];

        if (!is_valid_status(status)) {
            stats.invalid++;
            stats.errors.push_back(
                "Invalid status '" + status + "' for " + name + " (" + line + ")");
            continue;
        }

        // Match by (name, line) — find the station ID
        bool found = false;
        auto it = name_index_.find(name);
        if (it != name_index_.end()) {
            for (const auto& id : it->second) {
                auto sit = stations_.find(id);
                if (sit != stations_.end() && sit->second.line == line) {
                    sit->second.status = status;
                    stats.updated++;
                    found = true;
                    break;
                }
            }
        }

        if (!found) {
            stats.not_found++;
            stats.errors.push_back(
                "Station not found: " + name + " (" + line + ")");
        }
    }

    return stats;
}

bool StationManager::restore_initial(const std::filesystem::path& init_csv) {
    try {
        load(init_csv);
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[错误] 恢复初始状态失败: " << e.what() << "\n";
        return false;
    }
}

} // namespace metro
