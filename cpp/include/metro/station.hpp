#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <unordered_map>
#include <filesystem>

namespace metro {

// ---------------------------------------------------------------------------
// Station — a single metro station node (split by line for transfers)
// ---------------------------------------------------------------------------
struct Station {
    std::string id;       // "0101" = line 01, sequence 01
    std::string name;     // Chinese name, UTF-8
    std::string line;     // "1号线", "浦江线", etc.
    std::string status;   // "开启" or "关闭"

    bool is_open() const noexcept { return status == "开启"; }
};

// ---------------------------------------------------------------------------
// StationManager — station registry with name/line indexes
// ---------------------------------------------------------------------------
class StationManager {
public:
    StationManager() = default;

    // --- I/O ---
    void load(const std::filesystem::path& csv_path);
    void save(const std::filesystem::path& csv_path) const;

    // --- Query (returns nullptr when not found) ---
    const Station* get(const std::string& id) const;
    std::vector<const Station*> all_stations() const;
    std::vector<const Station*> find_by_name(const std::string& name) const;
    std::vector<const Station*> find_fuzzy(const std::string& keyword) const;
    std::vector<const Station*> stations_of_line(const std::string& line) const;
    std::vector<const Station*> closed_stations() const;
    std::vector<std::string> transfer_lines_for(
        const std::string& station_name,
        const std::string& exclude_line = "") const;

    // --- Status modification ---
    bool set_status(const std::string& id, const std::string& status);
    bool close_station(const std::string& id);
    bool open_station(const std::string& id);

    // --- Batch operations ---
    struct BatchStats {
        int updated = 0;
        int not_found = 0;
        int invalid = 0;
        std::vector<std::string> errors;
    };
    BatchStats batch_update_from_csv(const std::filesystem::path& update_csv);

    // --- Restore ---
    bool restore_initial(const std::filesystem::path& init_csv);

    // --- Capacity ---
    size_t size() const noexcept { return stations_.size(); }
    bool empty() const noexcept { return stations_.empty(); }

    // --- Direct index access (read-only, for graph traversal) ---
    const std::unordered_map<std::string, Station>& stations() const noexcept {
        return stations_;
    }
    const std::unordered_map<std::string, std::vector<std::string>>&
    name_index() const noexcept { return name_index_; }
    const std::unordered_map<std::string, std::vector<std::string>>&
    line_index() const noexcept { return line_index_; }

private:
    std::unordered_map<std::string, Station> stations_;
    std::unordered_map<std::string, std::vector<std::string>> name_index_;
    std::unordered_map<std::string, std::vector<std::string>> line_index_;

    void rebuild_indexes();
};

} // namespace metro
