#include "metro/network_analysis.hpp"
#include "metro/graph.hpp"
#include "metro/station.hpp"

#include <queue>
#include <stack>
#include <unordered_set>
#include <algorithm>

namespace metro::analysis {

// ---------------------------------------------------------------------------
// affected_area — BFS K-order neighbor analysis
// ---------------------------------------------------------------------------

std::vector<std::string> affected_area(const Graph& graph,
                                        const StationManager& mgr,
                                        const std::string& station_id,
                                        int max_depth) {
    std::vector<std::string> result;
    std::unordered_set<std::string> visited;
    std::queue<std::pair<std::string, int>> q;  // (node_id, depth)

    q.push({station_id, 0});
    visited.insert(station_id);

    const auto& adj = graph.adj();

    while (!q.empty()) {
        auto [cur, depth] = q.front(); q.pop();

        if (depth >= max_depth) continue;

        auto it = adj.find(cur);
        if (it == adj.end()) continue;

        for (const auto& edge : it->second) {
            const auto& next_id = edge.to_id;
            if (visited.count(next_id)) continue;
            visited.insert(next_id);

            // Only include open stations in affected area
            const Station* station = mgr.get(next_id);
            if (station && station->is_open()) {
                result.push_back(next_id);
            }

            q.push({next_id, depth + 1});
        }
    }

    // Sort for deterministic output
    std::sort(result.begin(), result.end());
    return result;
}

// ---------------------------------------------------------------------------
// count_components — DFS connected components
// ---------------------------------------------------------------------------

std::vector<std::vector<std::string>> count_components(
    const Graph& graph,
    const StationManager& mgr) {

    std::unordered_set<std::string> visited;
    std::vector<std::vector<std::string>> components;

    const auto& adj = graph.adj();

    // Iterative DFS over all open stations
    for (const auto& [id, s] : mgr.stations()) {
        if (!s.is_open()) continue;
        if (visited.count(id)) continue;

        std::vector<std::string> component;
        std::stack<std::string> stack;
        stack.push(id);

        while (!stack.empty()) {
            std::string node = stack.top(); stack.pop();
            if (visited.count(node)) continue;
            visited.insert(node);
            component.push_back(node);

            auto it = adj.find(node);
            if (it == adj.end()) continue;

            for (const auto& edge : it->second) {
                const auto& next_id = edge.to_id;
                if (visited.count(next_id)) continue;

                const Station* station = mgr.get(next_id);
                if (!station || !station->is_open()) {
                    visited.insert(next_id);  // mark as visited to skip
                    continue;
                }

                stack.push(next_id);
            }
        }

        if (!component.empty()) {
            components.push_back(std::move(component));
        }
    }

    // Sort by size descending (largest component first)
    std::sort(components.begin(), components.end(),
              [](const auto& a, const auto& b) {
                  return a.size() > b.size();
              });

    return components;
}

} // namespace metro::analysis
