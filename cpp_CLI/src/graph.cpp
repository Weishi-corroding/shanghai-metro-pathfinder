// graph.cpp —— 实现见 graph.hpp 头文件说明。
#include "graph.hpp"
#include "csv.hpp"
#include "station.hpp"

#include <iostream>
#include <stdexcept>

namespace mini {

void Graph::load(const std::filesystem::path& csv) {
    adj_.clear();
    edge_count_ = 0;
    auto rows = read_csv(csv);
    if (rows.empty()) throw std::runtime_error("Edge.csv 为空");
    // 表头：起点站ID, 终点站ID, 线路, 运行方向, 通行时间
    // 不合规的行会被跳过但累计计数；结束时 stderr 输出一条警告，方便定位
    // 数据问题（否则路径搜索会报"未找到可达路径"却查不出原因）。
    int skipped = 0;
    for (size_t i = 1; i < rows.size(); ++i) {
        const auto& r = rows[i];
        if (r.size() < 5) { ++skipped; continue; }
        Edge e;
        e.from_id = trim(r[0]);
        e.to_id   = trim(r[1]);
        e.line    = trim(r[2]);
        e.direction = trim(r[3]);
        try { e.time = std::stoi(trim(r[4])); }
        catch (...) { ++skipped; continue; }
        if (e.from_id.empty() || e.to_id.empty()) { ++skipped; continue; }
        adj_[e.from_id].push_back(e);
        // 终点也插入 adj_（空 vector），让 node_count() 报告准确的节点总数——
        // 即使某节点只有入边没出边。
        if (!adj_.count(e.to_id)) adj_[e.to_id] = {};
        ++edge_count_;
    }
    if (skipped > 0) {
        std::cerr << "[警告] Edge.csv 跳过 " << skipped
                  << " 行（字段不足或时间字段非法）\n";
    }
}

const std::vector<Edge>& Graph::neighbors(const std::string& id) const {
    // 返回内部 vector 的常量引用，避免每次 Dijkstra 松弛都拷贝边数组。
    // 未知 id 返回静态 empty —— 避免插入空项污染 adj_。
    static const std::vector<Edge> empty;
    auto it = adj_.find(id);
    return it == adj_.end() ? empty : it->second;
}

const Edge* Graph::get_edge(const std::string& from,
                             const std::string& to) const {
    auto it = adj_.find(from);
    if (it == adj_.end()) return nullptr;
    // 线性扫描：每个站点出度极小（~3 条），无需建二级索引
    for (const auto& e : it->second) {
        if (e.to_id == to) return &e;
    }
    return nullptr;
}

} // namespace mini
