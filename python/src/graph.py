"""
graph.py — 地铁网络图建模
==========================

Graph 类维护邻接表结构 + 站名 ↔ ID 双索引。

与 StationManager 配合使用：
  - StationManager 管理站点状态（开启/关闭）
  - Graph 在查询时通过 StationManager 过滤关闭节点
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from station import StationManager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EDGE_CSV = DATA_DIR / "Edge.csv"


# ---------------------------------------------------------------------------
# Edge 数据类
# ---------------------------------------------------------------------------

@dataclass
class Edge:
    """有向边"""
    from_id: str
    to_id: str
    line: str           # "1号线" 或 "换乘"
    direction: str      # "往富锦路" 或 ""（换乘边无方向）
    time: int           # 通行时间（分钟）

    @property
    def is_transfer(self) -> bool:
        return self.line == "换乘"

    def __repr__(self) -> str:
        return f"{self.from_id} -> {self.to_id} [{self.line}] {self.time}min"


# ---------------------------------------------------------------------------
# Graph 类
# ---------------------------------------------------------------------------

class Graph:
    """地铁网络有向图。

    数据结构：邻接表 — dict[from_id, list[Edge]]
    使用时传入 StationManager 来过滤关闭节点。

    用法:
        graph = Graph(EDGE_CSV)
        station_mgr = StationManager()
        station_mgr.load()

        # 获取邻居（自动过滤关闭站点）
        for edge in graph.neighbors("0101", station_mgr):
            print(edge.to_id, edge.time)
    """

    def __init__(self) -> None:
        self._adj: dict[str, list[Edge]] = defaultdict(list)
        self._edge_count = 0

    # -------- 加载 --------

    def load(self, csv_path: Path = EDGE_CSV) -> None:
        """从 Edge.csv 加载边数据。"""
        self._adj.clear()
        self._edge_count = 0

        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                edge = Edge(
                    from_id=row["起点站ID"],
                    to_id=row["终点站ID"],
                    line=row["线路"],
                    direction=row["运行方向"],
                    time=int(row["通行时间"]),
                )
                self._adj[edge.from_id].append(edge)
                self._edge_count += 1

    def load_from_edges(self, edges: list[Edge]) -> None:
        """从 Edge 列表加载（用于测试）。"""
        self._adj.clear()
        self._edge_count = 0
        for e in edges:
            self._adj[e.from_id].append(e)
            self._edge_count += 1

    # -------- 查询 --------

    def neighbors(self, station_id: str,
                  station_mgr: StationManager | None = None) -> list[Edge]:
        """获取邻居边。

        如果传入了 station_mgr，会自动过滤：
          - 终点站已关闭的边
          - 终点站不存在的边
        """
        edges = list(self._adj.get(station_id, []))
        if station_mgr is None:
            return edges

        filtered = []
        for e in edges:
            target = station_mgr.get(e.to_id)
            if target is not None and target.is_open:
                filtered.append(e)
        return filtered

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """判断是否有直达边。"""
        return any(e.to_id == to_id for e in self._adj.get(from_id, []))

    def get_edge(self, from_id: str, to_id: str) -> Edge | None:
        """获取特定边（用于查权重）。"""
        for e in self._adj.get(from_id, []):
            if e.to_id == to_id:
                return e
        return None

    @property
    def node_count(self) -> int:
        """返回图中的节点数。"""
        return len(self._adj)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def all_ids(self) -> set[str]:
        """返回图中所有节点 ID。"""
        ids: set[str] = set()
        for from_id, edges in self._adj.items():
            ids.add(from_id)
            for e in edges:
                ids.add(e.to_id)
        return ids


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    graph = Graph()
    graph.load()
    print(f"图加载完成: {graph.node_count} 节点, {graph.edge_count} 条边")

    # 验证 1 号线 莘庄 -> 外环路
    edges = graph.neighbors("0101")
    for e in edges:
        if e.to_id == "0102":
            print(f"莘庄(0101) -> 外环路(0102): time={e.time}min, line={e.line}")

    # 验证换乘边
    station_ids = {"0101", "0501"}  # 莘庄(1号线) -> 莘庄(5号线)
    edges = graph.neighbors("0101")
    for e in edges:
        if e.is_transfer:
            print(f"换乘边示例: {e}")