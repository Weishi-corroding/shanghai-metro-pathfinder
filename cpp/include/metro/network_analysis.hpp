#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace metro {

class Graph;
class StationManager;

namespace analysis {

// BFS K-order neighbor analysis for closed station impact
// Returns list of affected station IDs up to max_depth hops away.
std::vector<std::string> affected_area(const Graph& graph,
                                        const StationManager& mgr,
                                        const std::string& station_id,
                                        int max_depth = 2);

// DFS connected components of open stations
// Returns components sorted by size descending.
std::vector<std::vector<std::string>> count_components(
    const Graph& graph,
    const StationManager& mgr);

} // namespace analysis
} // namespace metro
