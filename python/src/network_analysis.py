"""
network_analysis.py — 网络分析功能
====================================

提供：
  - affected_area()     受关闭站点影响分析（BFS K 阶邻居）
  - count_components()  全网连通分量检测（DFS）
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph import Graph
    from station import StationManager


def affected_area(graph: Graph,
                  station_mgr: StationManager,
                   station_id: str,
                   max_depth: int = 2) -> list[str]:
    """BFS 查找受关闭站点影响的 K 阶邻居（不含关闭站本身）。

    参数:
      station_id: 被关闭的站点 ID
      max_depth:  分析深度（默认 2 阶）

    返回: [affected_station_id, ...]（按 BFS 顺序）
    """
    if max_depth <= 0:
        return []

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    affected: list[str] = []

    station = station_mgr.get(station_id)
    if station is None:
        return []

    queue.append((station_id, 0))
    visited.add(station_id)

    while queue:
        cur, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for edge in graph._adj.get(cur, []):
            neighbor = edge.to_id
            if neighbor not in visited:
                visited.add(neighbor)
                # 只算其他线路上同名站点的受影响
                ns = station_mgr.get(neighbor)
                if ns and ns.is_open:
                    affected.append(neighbor)
                    queue.append((neighbor, depth + 1))

    return affected


def count_components(graph: Graph,
                     station_mgr: StationManager) -> list[list[str]]:
    """DFS 求连通分量（仅考虑开启的站点）。

    返回: [[component_station_ids], ...]，按分量大小降序
    """
    visited: set[str] = set()
    components: list[list[str]] = []

    def dfs(node: str, comp: list[str]) -> None:
        visited.add(node)
        comp.append(node)
        for edge in graph._adj.get(node, []):
            neighbor = edge.to_id
            if neighbor not in visited:
                ns = station_mgr.get(neighbor)
                if ns is None or not ns.is_open:
                    continue
                dfs(neighbor, comp)

    all_ids = graph.all_ids()
    for sid in all_ids:
        if sid in visited:
            continue
        s = station_mgr.get(sid)
        if s is None or not s.is_open:
            visited.add(sid)
            continue
        comp: list[str] = []
        dfs(sid, comp)
        components.append(comp)

    components.sort(key=len, reverse=True)
    return components


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

    # 关闭一个站
    for s in mgr.find_by_name("漕宝路"):
        if "1号线" in s.line:
            mgr.close_station(s.station_id)
            print(f"关闭 {s}")

    # 受影响分析
    print(f"\n受影响站点（1阶）:")
    for s in mgr.find_by_name("漕宝路"):
        if not s.is_open:
            affected = affected_area(g, mgr, s.station_id, max_depth=1)
            for aid in affected:
                ns = mgr.get(aid)
                if ns:
                    print(f"  {ns}")

    # 连通分量
    print(f"\n连通分量:")
    comps = count_components(g, mgr)
    print(f"总分量数: {len(comps)}")
    for i, comp in enumerate(comps[:3]):
        print(f"  分量 {i+1}: {len(comp)} 个节点")

    # 恢复
    mgr.restore_initial()