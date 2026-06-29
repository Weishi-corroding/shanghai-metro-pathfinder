// graph.hpp —— 地铁路网的有向多重图（邻接表）
//
// 两类有向边：
//   • 乘车边：line="1号线" 等具体线路名，time = 实际通行时间（分钟）
//   • 换乘边：line="换乘"，time=5，连接同一物理站的两个不同线路节点
//
// 由于上下行时间可能不同，每段相邻区间在 Edge.csv 中以两条独立有向边表达。
// 4 号线环线方向通过 direction 字段（"内"/"外"）区分。
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <filesystem>

namespace mini {

class StationManager;

struct Edge {
    std::string from_id;
    std::string to_id;
    std::string line;       // "1号线" 或 "换乘"
    std::string direction;  // "往莘庄" / "内圈" / "外圈"，换乘边为空
    int time = 0;           // 通行时间（分钟）
    bool is_transfer() const { return line == "换乘"; }
};

class Graph {
public:
    // 从 Edge.csv 装入。表头：起点ID, 终点ID, 线路, 运行方向, 通行时间。
    // 缺字段或非法时间字段的行会被跳过，并在 stderr 输出一条警告。
    void load(const std::filesystem::path& csv);

    // 返回 `id` 的所有出边引用（含换乘边），不复制 Edge 字段。
    // 注意：关闭站点过滤 *不* 在这里做（单一职责）；调用方按需在松弛循环里
    // 用 pathfinder.cpp 的 target_open(m, e) 辅助函数内联过滤。
    // 未知 id 返回 static 空 vector 的引用。
    const std::vector<Edge>& neighbors(const std::string& id) const;

    // 查找特定有向边；不存在时返回 nullptr。
    const Edge* get_edge(const std::string& from, const std::string& to) const;

    size_t node_count() const { return adj_.size(); }
    size_t edge_count() const { return edge_count_; }

    std::unordered_set<std::string> all_ids() const;
    // 原始邻接表（只读访问），网络分析函数直接遍历
    const std::unordered_map<std::string, std::vector<Edge>>& adj() const { return adj_; }

private:
    std::unordered_map<std::string, std::vector<Edge>> adj_;
    size_t edge_count_ = 0;
};

} // namespace mini
