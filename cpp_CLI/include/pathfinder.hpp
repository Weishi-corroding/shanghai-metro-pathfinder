// pathfinder.hpp —— 路径规划与网络分析接口
//
// 该头文件声明：
//   • PathResult 结构 ——「路径 + 累计耗时 + 换乘次数 + 换乘点 + 错误信息」
//   • pf 命名空间下 4 个路径算法对外入口（M3-1/2 + M4-1/2）
//   • format()：把 PathResult 渲染为控制台多行字符串
//   • affected_area() / component_count()：BFS 波及范围 + DFS 连通分量
//
// 详细实现及关键设计权衡见 pathfinder.cpp 顶部注释。
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <tuple>

namespace mini {

class Graph;
class StationManager;

// PathResult —— 单次路径规划的完整结果包。
//   ids[]:        节点 ID 序列（含拆分后的换乘节点）
//   total_time:   累计通行时间（分钟，含 5 min 换乘惩罚）
//   transfers:    换乘次数（按乘客视角，末段进站换站台不计入）
//   transfer_at:  (站名, 旧线路, 新线路) 三元组列表，便于汇总展示
//   line4_dirs:   4 号线节点的内/外圈方向标签（id -> "内圈"/"外圈"）
//   valid/error:  搜索失败或前置校验失败时为 false + 中文错误信息
struct PathResult {
    std::vector<std::string> ids;
    int total_time = 0;
    int transfers = 0;
    // (station_name, from_line, to_line)
    std::vector<std::tuple<std::string, std::string, std::string>> transfer_at;
    // station_id -> "内圈" / "外圈" (only for 4 号线 segments)
    std::unordered_map<std::string, std::string> line4_dirs;
    bool valid = true;
    std::string error;
};

namespace pf {

// --- 路径规划 ---------------------------------------------------------------
PathResult shortest_time(const std::string& src, const std::string& dst,
                          const Graph& g, const StationManager& m);

std::vector<PathResult> k_shortest_time(const std::string& src,
                                         const std::string& dst,
                                         const Graph& g,
                                         const StationManager& m,
                                         int k = 3);

PathResult min_transfers(const std::string& src, const std::string& dst,
                          const Graph& g, const StationManager& m);

std::vector<PathResult> k_min_transfers(const std::string& src,
                                         const std::string& dst,
                                         const Graph& g,
                                         const StationManager& m,
                                         int k = 3);

// 将路径结果格式化为多行控制台字符串
std::string format(const PathResult& r, const StationManager& m, const Graph& g);

// --- 网络分析 ---------------------------------------------------------------
// 关闭某站后受波及的 order 阶邻接站点（按物理拓扑，忽略换乘边、跳过关闭站）
std::vector<std::string> affected_area(const std::string& src_id,
                                        const Graph& g,
                                        const StationManager& m,
                                        int order);

// 当前开放子图的连通分量数（仅统计开放站点，换乘边参与连通性判断）
int component_count(const Graph& g, const StationManager& m);

} // namespace pf
} // namespace mini
