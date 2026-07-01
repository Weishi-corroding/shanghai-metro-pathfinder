#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <unordered_map>
#include <tuple>

namespace metro {

class Graph;
class StationManager;

// ---------------------------------------------------------------------------
// PathResult — encapsulated result of a single path query
// ---------------------------------------------------------------------------
struct PathResult {
    std::vector<std::string> station_ids;  // ordered station ID list
    int total_time = 0;
    int transfer_count = 0;
    // Number of transfer (换乘) edges traversed. Each transfer edge connects two
    // line-nodes of the SAME physical station, so it must be subtracted when
    // reporting the count of distinct physical stations passed (途经站数).
    int transfer_edge_count = 0;
    // transfer_at: (station_name, from_line, to_line)
    std::vector<std::tuple<std::string, std::string, std::string>> transfer_at;
    // line4_dirs: station_id → direction tag ("内圈" or "外圈")
    std::unordered_map<std::string, std::string> line4_dirs;
    bool valid = true;
    std::string error;

    // Distinct physical stations on the route. Transfer-platform nodes of the
    // same physical station collapse into one (each transfer edge merges two
    // adjacent nodes), so we subtract the transfer-edge count. Safe for
    // single-id / empty / error paths (transfer_edge_count defaults to 0).
    size_t station_count() const noexcept {
        size_t n = station_ids.size();
        size_t x = static_cast<size_t>(transfer_edge_count);
        return n > x ? n - x : n;
    }
};

// ---------------------------------------------------------------------------
// pathfinder — namespace of free functions (no state)
// ---------------------------------------------------------------------------
namespace pathfinder {

// M3-1: Single shortest-time path
PathResult dijkstra_shortest_time(const std::string& src_id,
                                   const std::string& dst_id,
                                   const Graph& graph,
                                   const StationManager& mgr);

// M3-2: Yen K-shortest time paths
std::vector<PathResult> yen_k_shortest_time(const std::string& src_id,
                                             const std::string& dst_id,
                                             const Graph& graph,
                                             const StationManager& mgr,
                                             int k = 3);

// M4-1: Single min-transfer path
PathResult dijkstra_min_transfers(const std::string& src_id,
                                   const std::string& dst_id,
                                   const Graph& graph,
                                   const StationManager& mgr);

// M4-2: Yen K-min-transfer paths
std::vector<PathResult> yen_k_min_transfers(const std::string& src_id,
                                             const std::string& dst_id,
                                             const Graph& graph,
                                             const StationManager& mgr,
                                             int k = 3);

// Format a PathResult for console display
std::string format_path(const PathResult& result,
                        const StationManager& mgr,
                        const Graph* graph = nullptr);

} // namespace pathfinder
} // namespace metro
