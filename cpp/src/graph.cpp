#include "metro/graph.hpp"
#include "metro/station.hpp"
#include "metro/csv.hpp"

namespace metro {

// ---------------------------------------------------------------------------
// I/O
// ---------------------------------------------------------------------------

void Graph::load(const std::filesystem::path& csv_path) {
    csv::Reader reader(csv_path);

    adj_.clear();
    edge_count_ = 0;

    for (auto& row : reader.read_all()) {
        Edge e;
        e.from_id   = row["起点站ID"];
        e.to_id     = row["终点站ID"];
        e.line      = row["线路"];
        e.direction = row["运行方向"];
        e.time      = std::stoi(row["通行时间"]);

        adj_[e.from_id].push_back(e);
        ++edge_count_;

        // Ensure the destination node exists in adjacency map
        // (so node_count() includes sink nodes)
        if (adj_.find(e.to_id) == adj_.end()) {
            adj_[e.to_id] = {};
        }
    }
}

// ---------------------------------------------------------------------------
// Traversal
// ---------------------------------------------------------------------------

std::vector<Edge> Graph::neighbors(const std::string& station_id,
                                    const StationManager* mgr) const {
    auto it = adj_.find(station_id);
    if (it == adj_.end()) {
        return {};
    }

    if (mgr == nullptr) {
        return it->second;
    }

    // Filter: exclude edges whose target station is closed or missing
    std::vector<Edge> result;
    result.reserve(it->second.size());
    for (const auto& e : it->second) {
        const Station* target = mgr->get(e.to_id);
        // If target doesn't exist in station manager, skip it
        if (target == nullptr) continue;
        // If target is closed, skip it (transfer edges are never blocked,
        // because the transfer station node itself is separate from line nodes)
        if (!target->is_open()) continue;
        result.push_back(e);
    }
    return result;
}

// ---------------------------------------------------------------------------
// Lookup
// ---------------------------------------------------------------------------

bool Graph::has_edge(const std::string& from, const std::string& to) const {
    auto it = adj_.find(from);
    if (it == adj_.end()) return false;

    for (const auto& e : it->second) {
        if (e.to_id == to) return true;
    }
    return false;
}

const Edge* Graph::get_edge(const std::string& from, const std::string& to) const {
    auto it = adj_.find(from);
    if (it == adj_.end()) return nullptr;

    for (const auto& e : it->second) {
        if (e.to_id == to) return &e;
    }
    return nullptr;
}

} // namespace metro
