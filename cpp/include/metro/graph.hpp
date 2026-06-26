#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <filesystem>

namespace metro {

class StationManager;

// ---------------------------------------------------------------------------
// Edge — a directed edge in the metro graph
// ---------------------------------------------------------------------------
struct Edge {
    std::string from_id;
    std::string to_id;
    std::string line;       // "1号线" or "换乘"
    std::string direction;  // "往富锦路" or "" for transfer edges
    int time = 0;           // travel time in minutes

    bool is_transfer() const noexcept { return line == "换乘"; }
};

// ---------------------------------------------------------------------------
// Graph — adjacency-list representation of the metro network
// ---------------------------------------------------------------------------
class Graph {
public:
    Graph() = default;

    // --- I/O ---
    void load(const std::filesystem::path& csv_path);
    void load_from_edges(const std::vector<Edge>& edges);

    // --- Traversal ---
    // Returns outgoing edges. When mgr is provided, filters edges whose
    // target station is closed or missing.
    std::vector<Edge> neighbors(const std::string& station_id,
                                const StationManager* mgr = nullptr) const;

    // --- Lookup ---
    bool has_edge(const std::string& from, const std::string& to) const;
    const Edge* get_edge(const std::string& from, const std::string& to) const;

    // --- Capacity ---
    size_t node_count() const noexcept { return adj_.size(); }
    size_t edge_count() const noexcept { return edge_count_; }

    // --- All node IDs ---
    std::unordered_set<std::string> all_ids() const;

    // --- Direct adjacency access (read-only, for network analysis) ---
    const std::unordered_map<std::string, std::vector<Edge>>& adj() const noexcept {
        return adj_;
    }

private:
    std::unordered_map<std::string, std::vector<Edge>> adj_;
    size_t edge_count_ = 0;
};

} // namespace metro
