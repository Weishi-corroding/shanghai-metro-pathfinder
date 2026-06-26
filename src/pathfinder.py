"""
pathfinder.py — 路径规划算法引擎（M3/M4 模块）
================================================

核心算法：
  - dijkstra_shortest_time()       单条最短时间路径（M3-1）
  - yen_k_shortest_time()          K 条最短时间路径（M3-2，K=3）
  - dijkstra_min_transfers()       单条最少换乘路径（M4-1，元组权）
  - yen_k_min_transfers()          K 条最少换乘路径（M4-2）

路径可视化辅助：
  - PathResult 类封装路径信息
  - format_path() 格式化终端输出
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph import Graph, Edge
    from station import StationManager

# 换乘识别常量
TRANSFER_LINE = "换乘"

# 4 号线方向关键词
LINE4_INNER = "内"     # 逆时针
LINE4_OUTER = "外"     # 顺时针


# ---------------------------------------------------------------------------
# PathResult — 单条路径的结果封装
# ---------------------------------------------------------------------------

@dataclass
class PathResult:
    """一条完整路径的结果。

    Attributes:
        station_ids    路径经过的站点 ID 列表（含起终点，不含换乘虚拟节点）
        total_time     总耗时（分钟，含换乘惩罚）
        transfer_count 换乘次数
        transfer_at    换乘点 [(站名, 从线路, 到线路), ...]
        line4_dirs     4 号线区间标记 {(站点ID): "外圈"|"内圈", ...}
        valid          是否有效路径
        error          无效时的错误说明
    """
    station_ids: list[str] = field(default_factory=list)
    total_time: int = 0
    transfer_count: int = 0
    transfer_at: list[tuple[str, str, str]] = field(default_factory=list)
    line4_dirs: dict[str, str] = field(default_factory=dict)
    valid: bool = True
    error: str = ""

    @property
    def station_count(self) -> int:
        """实际经过的物理站点数（不含换乘虚拟节点）。"""
        return len(self.station_ids)


# ---------------------------------------------------------------------------
# 内部数据结构
# ---------------------------------------------------------------------------

@dataclass(order=True)
class _PqItem:
    """优先队列元素（时间/换乘权重, 当前站ID, 路径前驱, 当前线路, 换乘次数, 4号线方向）"""
    weight: tuple = field(default_factory=lambda: (0,))  # (time,) 或 (transfers, time)
    node: str = ""
    prev: str = ""
    line: str = ""    # 进入本节点的边所属线路
    transfers: int = 0
    line4_dir: str = ""  # 4 号线当前方向


def _rebuild_path(end: str, came_from: dict,
                  graph: Graph, station_mgr: StationManager) -> PathResult:
    """从 came_from 回溯重建完整路径并计算换乘信息。"""

    # 回溯节点序列（起 → 终）
    path_ids: list[str] = []
    curr = end
    while curr:
        path_ids.append(curr)
        prev_info = came_from.get(curr)
        if prev_info is None:
            break
        curr = prev_info.get("prev", "")

    path_ids.reverse()

    result = PathResult(station_ids=path_ids)

    # 扫描所有连续边，记录非换乘边的线路 sequence
    # 并检查是否有换乘边（在非换乘边之间的换乘连接）
    total_time = 0
    line_trace: list[tuple[str, str, str]] = []  # [(station_id, line, station_name), ...]

    # 首先记录起点站的线路（从 station_mgr 获取）
    src_station = station_mgr.get(path_ids[0])
    if src_station:
        line_trace.append((path_ids[0], src_station.line, src_station.name))

    for i in range(1, len(path_ids)):
        edge = graph.get_edge(path_ids[i - 1], path_ids[i])
        if edge is None:
            continue
        total_time += edge.time

        if not edge.is_transfer:
            station = station_mgr.get(path_ids[i - 1])
            sname = station.name if station else ""
            # 如果这条非换乘边紧接着换乘边，它的线路与前一条非换乘边的线路比较
            line_trace.append((path_ids[i - 1], edge.line, sname))

            # 4 号线方向标记（key=站点ID，避免环线同名站冲突）
            if "4号线" in edge.line and edge.direction:
                target_id = path_ids[i]
                if LINE4_INNER in edge.direction:
                    result.line4_dirs[target_id] = "内圈"
                elif LINE4_OUTER in edge.direction:
                    result.line4_dirs[target_id] = "外圈"

    result.total_time = total_time

    # 从 line_trace 计算换乘次数和换乘点
    transfers = 0
    transfer_at: list[tuple[str, str, str]] = []
    if line_trace:
        current_line = line_trace[0][1]
        for j in range(1, len(line_trace)):
            if line_trace[j][1] != current_line:
                # 线路变化！在 line_trace[j][0] 处发生换乘
                transfers += 1
                _, new_line, sname = line_trace[j]
                # 避免同一站重复计数
                if not transfer_at or transfer_at[-1][0] != sname:
                    transfer_at.append((sname, current_line, new_line))
                current_line = new_line

    result.transfer_count = transfers
    result.transfer_at = transfer_at
    result.valid = True
    return result


# ---------------------------------------------------------------------------
# 辅助：路径去重（用于 Yen 算法）
# ---------------------------------------------------------------------------

def _path_key(station_ids: list[str]) -> str:
    """路径唯一标识：站点序列字符串。"""
    return "->".join(station_ids)


# ---------------------------------------------------------------------------
# M3-1: Dijkstra 最短时间路径
# ---------------------------------------------------------------------------

def dijkstra_shortest_time(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
) -> PathResult:
    """Dijkstra + 优先队列，计算最短时间路径。

    换乘惩罚已包含在换乘边权重（5min）中。
    """
    if src_id == dst_id:
        return PathResult(valid=True, station_ids=[src_id], total_time=0,
                          error="起点和终点相同，无需进行路径规划。")

    # 检查起终点是否开启
    src_station = station_mgr.get(src_id)
    dst_station = station_mgr.get(dst_id)
    if src_station and not src_station.is_open:
        return PathResult(valid=False, error=f"起点：{src_station}已关闭，无法进行路径规划。")
    if dst_station and not dst_station.is_open:
        return PathResult(valid=False, error=f"终点：{dst_station}已关闭，无法进行路径规划。")

    dist: dict[str, int] = {src_id: 0}
    came_from: dict[str, dict | None] = {src_id: None}
    pq: list[tuple[int, str]] = [(0, src_id)]

    visited: set[str] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if u == dst_id:
            return _rebuild_path(dst_id, came_from, graph, station_mgr)

        for edge in graph.neighbors(u, station_mgr):
            v = edge.to_id
            nd = d + edge.time
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                came_from[v] = {"prev": u, "edge": edge}
                heapq.heappush(pq, (nd, v))

    return PathResult(valid=False, error="未找到可达路径。")


# ---------------------------------------------------------------------------
# M3-2: Yen K-最短时间路径
# ---------------------------------------------------------------------------

def yen_k_shortest_time(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
    k: int = 3,
) -> list[PathResult]:
    """Yen's K-Shortest Paths 算法，返回排序后的 Top-K 路径。"""
    if src_id == dst_id:
        p = PathResult(valid=True, station_ids=[src_id], total_time=0,
                       error="起点和终点相同，无需进行路径规划。")
        return [p]

    src_s = station_mgr.get(src_id)
    dst_s = station_mgr.get(dst_id)
    if src_s and not src_s.is_open:
        return [PathResult(valid=False, error=f"起点：{src_s}已关闭，无法进行路径规划。")]
    if dst_s and not dst_s.is_open:
        return [PathResult(valid=False, error=f"终点：{dst_s}已关闭，无法进行路径规划。")]

    # 1. 先求最短路径
    first = dijkstra_shortest_time(src_id, dst_id, graph, station_mgr)
    if not first.valid or not first.station_ids:
        return [first]

    a_paths: list[PathResult] = [first]
    candidates: list[tuple[int, list[str]]] = []  # (total_time, path_ids)

    for ki in range(1, k):
        n = len(a_paths[ki - 1].station_ids)
        for i in range(n - 1):
            # 暂存要删除的边和节点
            spur_node = a_paths[ki - 1].station_ids[i]

            # 收集已经输出的路径中从 spur_node 出发的相同前缀路径
            root_path = a_paths[ki - 1].station_ids[: i + 1]

            removed_edges: list[tuple[str, str]] = []
            removed_stations: list[str] = []

            for prev_path in a_paths:
                pp_ids = prev_path.station_ids
                if len(pp_ids) > i and pp_ids[: i + 1] == root_path:
                    # 暂时删除 edge(pp_ids[i], pp_ids[i + 1]) if exists
                    if i + 1 < len(pp_ids):
                        removed_edges.append((pp_ids[i], pp_ids[i + 1]))

            # 暂时删除 root_path 中除 spur_node 外的节点（防止走回头路）
            for sid in root_path[:-1]:
                if sid != spur_node:
                    removed_stations.append(sid)

            # 构建临时图或使用标记
            # 在路径计算时绕过删除的边和节点
            spur_path = _dijkstra_with_removals(
                spur_node, dst_id,
                graph, station_mgr,
                removed_edges=removed_edges,
                removed_stations=removed_stations,
            )

            if spur_path.valid and spur_path.station_ids:
                total_path = root_path[:-1] + spur_path.station_ids
                total_time = _path_total_time(total_path, graph)

                # 去重检查
                pk = _path_key(total_path)
                already_have = any(
                    _path_key(p.station_ids) == pk for p in a_paths
                )
                if not already_have:
                    heapq.heappush(candidates, (total_time, total_path))

        if not candidates:
            break

        # 提取最优候选
        while candidates:
            best_time, best_path = heapq.heappop(candidates)
            # 重建 PathResult
            result = _rebuild_path_from_ids(best_path, graph, station_mgr)
            if result.valid:
                a_paths.append(result)
                break

    return a_paths


def _dijkstra_with_removals(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
    removed_edges: list[tuple[str, str]],
    removed_stations: list[str],
) -> PathResult:
    """带临时边/节点删除的 Dijkstra。"""
    dist: dict[str, int] = {src_id: 0}
    came_from: dict[str, dict | None] = {src_id: None}
    pq: list[tuple[int, str]] = [(0, src_id)]
    visited: set[str] = set()
    removed_nodes = set(removed_stations)

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        if u in removed_nodes:
            continue
        visited.add(u)

        if u == dst_id:
            return _rebuild_path(dst_id, came_from, graph, station_mgr)

        for edge in graph.neighbors(u, station_mgr):
            v = edge.to_id
            if (u, v) in removed_edges:
                continue
            if v in removed_nodes:
                continue
            nd = d + edge.time
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                came_from[v] = {"prev": u, "edge": edge}
                heapq.heappush(pq, (nd, v))

    return PathResult(valid=False, error="Yen 子路径未找到。")


def _path_total_time(path_ids: list[str], graph: Graph) -> int:
    """计算路径总时间。"""
    total = 0
    for i in range(1, len(path_ids)):
        edge = graph.get_edge(path_ids[i - 1], path_ids[i])
        if edge:
            total += edge.time
    return total


def _rebuild_path_from_ids(
    path_ids: list[str],
    graph: Graph, station_mgr: StationManager,
) -> PathResult:
    """从 ID 列表重建 PathResult。"""
    return _rebuild_path(path_ids[-1],
                         {path_ids[i]: {"prev": path_ids[i - 1]}
                          for i in range(1, len(path_ids))},
                         graph, station_mgr)


# ---------------------------------------------------------------------------
# M4-1: Dijkstra 最少换乘路径（元组权重）
# ---------------------------------------------------------------------------

def _count_line_changes(path_ids: list[str], graph: Graph) -> int:
    """统计路径的换乘次数。"""
    if len(path_ids) < 2:
        return 0
    changes = 0
    prev_line = ""
    for i in range(1, len(path_ids)):
        edge = graph.get_edge(path_ids[i - 1], path_ids[i])
        if edge and not edge.is_transfer:
            if prev_line and prev_line != edge.line:
                changes += 1
            prev_line = edge.line
    return changes


def dijkstra_min_transfers(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
) -> PathResult:
    """以 (换乘次数, 总时间) 为权重的 Dijkstra，优先最少换乘。"""
    if src_id == dst_id:
        return PathResult(valid=True, station_ids=[src_id], total_time=0,
                          error="起点和终点相同，无需进行路径规划。")

    src_s = station_mgr.get(src_id)
    dst_s = station_mgr.get(dst_id)
    if src_s and not src_s.is_open:
        return PathResult(valid=False, error=f"起点：{src_s}已关闭，无法进行路径规划。")
    if dst_s and not dst_s.is_open:
        return PathResult(valid=False, error=f"终点：{dst_s}已关闭，无法进行路径规划。")

    # 权重 = (换乘次数, 总时间) —— 元组比较自动优先换乘次数
    dist: dict[str, tuple[int, int]] = {src_id: (0, 0)}
    came_from: dict[str, dict | None] = {src_id: None}
    pq: list[tuple[tuple[int, int], str]] = [((0, 0), src_id)]
    visited: set[str] = set()

    # 记录到达每个节点的线路
    node_line: dict[str, str] = {}

    while pq:
        w, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if u == dst_id:
            return _rebuild_path(dst_id, came_from, graph, station_mgr)

        cur_transfers, cur_time = w
        cur_line = node_line.get(u, "")

        for edge in graph.neighbors(u, station_mgr):
            v = edge.to_id
            new_time = cur_time + edge.time

            # 计算换乘次数变化
            new_transfers = cur_transfers
            if edge.is_transfer:
                # 换乘边本身不计入线路变更
                pass
            elif cur_line and edge.line != cur_line:
                new_transfers = cur_transfers + 1

            new_weight = (new_transfers, new_time)

            # 记录进入 v 的线路
            if not edge.is_transfer:
                v_line = edge.line
            else:
                v_line = cur_line  # 换乘后保持原线路

            if v not in dist or new_weight < dist[v]:
                if v_line:
                    node_line[v] = v_line
                dist[v] = new_weight
                came_from[v] = {"prev": u, "edge": edge}
                heapq.heappush(pq, (new_weight, v))

    return PathResult(valid=False, error="未找到可达路径。")


# ---------------------------------------------------------------------------
# M4-2: Yen K-最少换乘路径
# ---------------------------------------------------------------------------

def yen_k_min_transfers(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
    k: int = 3,
) -> list[PathResult]:
    """Yen's K-Shortest Paths 变体，元组权重 (换乘次数, 时间)。"""
    if src_id == dst_id:
        p = PathResult(valid=True, station_ids=[src_id], total_time=0,
                       error="起点和终点相同，无需进行路径规划。")
        return [p]

    src_s = station_mgr.get(src_id)
    dst_s = station_mgr.get(dst_id)
    if src_s and not src_s.is_open:
        return [PathResult(valid=False, error=f"起点：{src_s}已关闭，无法进行路径规划。")]
    if dst_s and not dst_s.is_open:
        return [PathResult(valid=False, error=f"终点：{dst_s}已关闭，无法进行路径规划。")]

    first = dijkstra_min_transfers(src_id, dst_id, graph, station_mgr)
    if not first.valid or not first.station_ids:
        return [first]

    a_paths: list[PathResult] = [first]
    candidates: list[tuple[tuple[int, int], list[str]]] = []  # weight, path_ids

    for ki in range(1, k):
        n = len(a_paths[ki - 1].station_ids)
        for i in range(n - 1):
            spur_node = a_paths[ki - 1].station_ids[i]
            root_path = a_paths[ki - 1].station_ids[: i + 1]

            removed_edges: list[tuple[str, str]] = []
            for prev_path in a_paths:
                pp_ids = prev_path.station_ids
                if len(pp_ids) > i and pp_ids[: i + 1] == root_path:
                    if i + 1 < len(pp_ids):
                        removed_edges.append((pp_ids[i], pp_ids[i + 1]))

            spur_result = _min_transfer_with_removals(
                spur_node, dst_id, graph, station_mgr,
                removed_edges=removed_edges,
                removed_stations=[sid for sid in root_path[:-1] if sid != spur_node],
            )

            if spur_result.valid and spur_result.station_ids:
                total_path = root_path[:-1] + spur_result.station_ids
                total_time = _path_total_time(total_path, graph)
                total_transfers = _count_line_changes(total_path, graph)
                weight: tuple[int, int] = (total_transfers, total_time)

                pk = _path_key(total_path)
                already_have = any(
                    _path_key(p.station_ids) == pk for p in a_paths
                )
                if not already_have:
                    heapq.heappush(candidates, (weight, total_path))

        if not candidates:
            break

        while candidates:
            best_w, best_path = heapq.heappop(candidates)
            result = _rebuild_path_from_ids(best_path, graph, station_mgr)
            if result.valid:
                a_paths.append(result)
                break

    return a_paths


def _min_transfer_with_removals(
    src_id: str, dst_id: str,
    graph: Graph, station_mgr: StationManager,
    removed_edges: list[tuple[str, str]],
    removed_stations: list[str],
) -> PathResult:
    """带删除的 Dijkstra（最少换乘权）。"""
    dist: dict[str, tuple[int, int]] = {src_id: (0, 0)}
    came_from: dict[str, dict | None] = {src_id: None}
    pq: list[tuple[tuple[int, int], str]] = [((0, 0), src_id)]
    visited: set[str] = set()
    removed_nodes = set(removed_stations)
    node_line: dict[str, str] = {src_id: ""}

    while pq:
        w, u = heapq.heappop(pq)
        if u in visited or u in removed_nodes:
            continue
        visited.add(u)

        if u == dst_id:
            return _rebuild_path(dst_id, came_from, graph, station_mgr)

        cur_transfers, cur_time = w
        cur_line = node_line.get(u, "")

        for edge in graph.neighbors(u, station_mgr):
            v = edge.to_id
            if (u, v) in removed_edges or v in removed_nodes:
                continue

            new_time = cur_time + edge.time
            new_transfers = cur_transfers
            if not edge.is_transfer and cur_line and edge.line != cur_line:
                new_transfers = cur_transfers + 1

            new_weight = (new_transfers, new_time)
            if not edge.is_transfer:
                v_line = edge.line
            else:
                v_line = cur_line

            if v not in dist or new_weight < dist[v]:
                if v_line:
                    node_line[v] = v_line
                dist[v] = new_weight
                came_from[v] = {"prev": u, "edge": edge}
                heapq.heappush(pq, (new_weight, v))

    return PathResult(valid=False, error="Yen 子路径未找到。")


# ---------------------------------------------------------------------------
# 路径格式化输出
# ---------------------------------------------------------------------------

def format_path(result: PathResult, station_mgr: StationManager,
                graph: Graph | None = None) -> str:
    """将 PathResult 格式化为控制台可视化输出。"""
    if not result.valid:
        return f"[错误] {result.error}"

    lines: list[str] = []
    total = result.total_time
    transfers = result.transfer_count

    # 如果起终点相同
    if len(result.station_ids) == 1:
        station = station_mgr.get(result.station_ids[0])
        name = station.name if station else result.station_ids[0]
        lines.append(f"{name}（起终点相同）")
        lines.append(f"总耗时: 0 分钟 | 换乘: 0 次")
        return "\n".join(lines)

    # 构建可视化路径
    path_str = ""
    station_count = 0

    for i, sid in enumerate(result.station_ids):
        station = station_mgr.get(sid)
        if station is None:
            continue

        name = station.name
        line = station.line

        # 检查前一站到本站的边是否为换乘边
        if i > 0 and graph:
            edge = graph.get_edge(result.station_ids[i - 1], sid)
            if edge and edge.is_transfer:
                path_str += " ──[换乘]── "
                continue

        if station_count > 0:
            path_str += " → "

        # 标记线路
        line_tag = f"({line})" if line else ""
        # 4 号线方向标记（用站点ID查找，避免环线同名站标错）
        l4_dir = result.line4_dirs.get(sid, "")
        if l4_dir:
            line_tag = f"({line}{l4_dir})"

        path_str += f"{name}{line_tag}"
        station_count += 1

    lines.append(path_str)
    lines.append("")
    lines.append(f"途经 {station_count} 站 | 总耗时: {total} 分钟 | 换乘: {transfers} 次")

    if result.transfer_at:
        lines.append("换乘点:")
        for t_name, f_line, t_line in result.transfer_at:
            lines.append(f"  · {t_name} ({f_line} → {t_line})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from graph import Graph
    from station import StationManager

    g = Graph()
    g.load()
    mgr = StationManager()
    mgr.load()

    # 起终点
    # 莘庄(0101) -> 人民广场(0113/1号线)
    src = "0101"  # 莘庄 1号线
    dst = "0113"  # 人民广场 1号线

    print("=== 最短时间路径 ===")
    result = dijkstra_shortest_time(src, dst, g, mgr)
    print(format_path(result, mgr))

    print("\n=== 3 条最短时间路径 ===")
    results = yen_k_shortest_time(src, dst, 3, g, mgr)
    for i, r in enumerate(results):
        print(f"\n--- 路径 {i+1} ---")
        print(format_path(r, mgr))

    print("\n=== 最少换乘路径（莘庄→龙阳路）===")
    # 莘庄(0101,1号线) -> 龙阳路(0216,2号线 或 1601,16号线或其他)
    # 找龙阳路
    longyang = mgr.find_by_name("龙阳路")
    if longyang:
        dst_l = longyang[0].station_id
        result = dijkstra_min_transfers(src, dst_l, g, mgr)
        print(format_path(result, mgr))

        print("\n=== 3 条最少换乘路径 ===")
        results = yen_k_min_transfers(src, dst_l, 3, g, mgr)
        for i, r in enumerate(results):
            print(f"\n--- 路径 {i+1} ---")
            print(format_path(r, mgr))
