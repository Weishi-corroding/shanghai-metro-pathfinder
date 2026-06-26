"""
station.py — 站点实体与运营状态管理（M2 模块）
================================================

定义 Station 数据类，以及 StationManager 提供：
  - 从 Station.csv 加载全网站点
  - 批量 CSV 状态更新（M2-1）
  - 手工状态更新（M2-2）
  - 显示当前关闭站点（M2-3）
  - 恢复所有站点初始状态（M2-4）
  - 显示线路站点信息（M2-5）

数据文件位于 D:/Code/metro/data/：
  - Station.csv          当前状态
  - Station_init.csv     初始状态备份（恢复用）
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

STATION_CSV = DATA_DIR / "Station.csv"
STATION_INIT_CSV = DATA_DIR / "Station_init.csv"

# 合法状态字符串
STATUS_OPEN = "开启"
STATUS_CLOSED = "关闭"
VALID_STATUS = {STATUS_OPEN, STATUS_CLOSED}


# ---------------------------------------------------------------------------
# Station 数据类
# ---------------------------------------------------------------------------

@dataclass
class Station:
    """单个站点实体（一个换乘站会拆成多个 Station 对象，每条线一个）"""
    station_id: str
    name: str
    line: str           # "1号线" 等
    status: str         # "开启" / "关闭"

    @property
    def is_open(self) -> bool:
        return self.status == STATUS_OPEN

    def __str__(self) -> str:
        flag = "" if self.is_open else " [关闭]"
        return f"{self.name}({self.line}){flag}"


# ---------------------------------------------------------------------------
# StationManager — 站点集合 + 状态管理
# ---------------------------------------------------------------------------

class StationManager:
    """全网站点的容器，提供状态查询和修改。

    用法:
        mgr = StationManager()
        mgr.load(STATION_CSV)
        mgr.close_station("0101")         # 关闭单个站点
        mgr.batch_update_from_csv(path)   # 批量更新
        mgr.save(STATION_CSV)             # 持久化
    """

    def __init__(self) -> None:
        # 站点存储
        self._stations: dict[str, Station] = {}             # id -> Station
        self._name_index: dict[str, list[str]] = defaultdict(list)  # name -> [id]
        self._line_index: dict[str, list[str]] = defaultdict(list)  # line -> [id]

    # -------- 加载/保存 --------

    def load(self, csv_path: Path = STATION_CSV) -> None:
        """从 CSV 加载站点。"""
        self._stations.clear()
        self._name_index.clear()
        self._line_index.clear()

        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                s = Station(
                    station_id=row["站点ID"],
                    name=row["站点名称"],
                    line=row["所属线路"],
                    status=row["运营状态"],
                )
                self._stations[s.station_id] = s
                self._name_index[s.name].append(s.station_id)
                self._line_index[s.line].append(s.station_id)

    def save(self, csv_path: Path = STATION_CSV) -> None:
        """写回 Station.csv（持久化当前状态）。"""
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["站点ID", "站点名称", "所属线路", "运营状态"])
            for s in self._stations.values():
                writer.writerow([s.station_id, s.name, s.line, s.status])

    # -------- 查询 --------

    def get(self, station_id: str) -> Station | None:
        return self._stations.get(station_id)

    def all_stations(self) -> list[Station]:
        return list(self._stations.values())

    def find_by_name(self, name: str) -> list[Station]:
        """精确名匹配（一个换乘站会返回多个不同线路的 Station）。"""
        return [self._stations[i] for i in self._name_index.get(name, [])]

    def find_fuzzy(self, keyword: str) -> list[Station]:
        """子串模糊匹配，返回所有名称含 keyword 的站点。"""
        if not keyword:
            return []
        keyword = keyword.strip()
        matched: list[Station] = []
        for name, ids in self._name_index.items():
            if keyword in name:
                for sid in ids:
                    matched.append(self._stations[sid])
        return matched

    def stations_of_line(self, line: str) -> list[Station]:
        """获取某条线路的所有站点（按 Station.csv 中的顺序，即物理运营顺序）。"""
        return [self._stations[i] for i in self._line_index.get(line, [])]

    def closed_stations(self) -> list[Station]:
        return [s for s in self._stations.values() if not s.is_open]

    def transfer_lines_for(self, station_name: str, exclude_line: str = "") -> list[str]:
        """获取站点的换乘线路（除自身线路外）。"""
        lines = []
        for sid in self._name_index.get(station_name, []):
            line = self._stations[sid].line
            if line and line != exclude_line:
                lines.append(line)
        return lines

    # -------- 状态修改 --------

    def set_status(self, station_id: str, status: str) -> bool:
        """单个站点设置状态。返回 True 表示成功。"""
        if status not in VALID_STATUS:
            return False
        if station_id not in self._stations:
            return False
        self._stations[station_id].status = status
        return True

    def close_station(self, station_id: str) -> bool:
        return self.set_status(station_id, STATUS_CLOSED)

    def open_station(self, station_id: str) -> bool:
        return self.set_status(station_id, STATUS_OPEN)

    # -------- M2-1: 批量 CSV 更新 --------

    def batch_update_from_csv(self, update_csv: Path) -> dict[str, int]:
        """从 update_station_status.csv 批量更新状态。

        预期 CSV 字段: 站点名称, 所属线路, 运营状态

        返回统计字典：
            updated  — 成功更新数
            not_found — 站点未找到数
            invalid  — 状态值非法数
            errors   — 文件级错误（含错误描述列表，否则空）

        若文件不存在/格式错误，返回 errors 中的描述。
        """
        stats = {"updated": 0, "not_found": 0, "invalid": 0, "errors": []}

        if not update_csv.exists():
            stats["errors"].append(f"更新文件不存在: {update_csv}")
            return stats

        try:
            with open(update_csv, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                required = {"站点名称", "所属线路", "运营状态"}
                if not required.issubset(set(reader.fieldnames or [])):
                    stats["errors"].append(
                        f"更新文件格式异常，缺少必需字段: {required - set(reader.fieldnames or [])}"
                    )
                    return stats

                rows = list(reader)
        except Exception as e:
            stats["errors"].append(f"读取更新文件失败: {e}")
            return stats

        if not rows:
            stats["errors"].append("未检测到有效更新记录")
            return stats

        # 同站点重复出现时，"以最后一次更新为准"
        # —— 顺序遍历，后面的覆盖前面的
        for row in rows:
            name = (row.get("站点名称") or "").strip()
            line = (row.get("所属线路") or "").strip()
            status = (row.get("运营状态") or "").strip()

            if status not in VALID_STATUS:
                stats["invalid"] += 1
                continue

            # 通过 (站点名称, 所属线路) 双主键匹配
            matched_ids = [
                sid for sid in self._name_index.get(name, [])
                if self._stations[sid].line == line
            ]
            if not matched_ids:
                stats["not_found"] += 1
                continue

            for sid in matched_ids:
                self._stations[sid].status = status
                stats["updated"] += 1

        return stats

    # -------- M2-4: 恢复初始状态 --------

    def restore_initial(self, init_csv: Path = STATION_INIT_CSV) -> bool:
        """从 Station_init.csv 恢复全部站点状态。"""
        if not init_csv.exists():
            return False
        try:
            with open(init_csv, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    sid = row["站点ID"]
                    if sid in self._stations:
                        self._stations[sid].status = row["运营状态"]
            return True
        except Exception:
            return False

    # -------- 工具：站点选择（含模糊匹配） --------

    def resolve_station(self, keyword: str, prompter=None) -> Station | None:
        """根据输入的关键词解析出唯一的 Station。

        - 无匹配 -> 返回 None
        - 唯一匹配 -> 直接返回
        - 多个匹配 -> 调用 prompter(matched_list) 让用户选择
          prompter 默认（None）下取第一个

        prompter 签名: (list[Station]) -> Station | None
        """
        matched = self.find_fuzzy(keyword)
        if not matched:
            return None
        if len(matched) == 1:
            return matched[0]
        if prompter is None:
            return matched[0]
        return prompter(matched)

    # -------- 工具：迭代支持 --------

    def __iter__(self):
        return iter(self._stations.values())

    def __len__(self):
        return len(self._stations)

    def __contains__(self, station_id: str) -> bool:
        return station_id in self._stations


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mgr = StationManager()
    mgr.load()
    print(f"加载站点数: {len(mgr)}")

    # 测试: 莘庄
    for s in mgr.find_by_name("莘庄"):
        print(f"  {s}")

    # 测试: 模糊匹配
    print("\n模糊匹配 '上海体':")
    for s in mgr.find_fuzzy("上海体"):
        print(f"  {s}")

    # 测试: 显示当前关闭
    print(f"\n当前关闭站点: {len(mgr.closed_stations())}")

    # 测试: 关闭一个站
    s = mgr.find_by_name("漕宝路")[0]
    mgr.close_station(s.station_id)
    print(f"关闭 {s.name} ({s.line}) -> 当前关闭数: {len(mgr.closed_stations())}")

    # 测试: 恢复初始
    if mgr.restore_initial():
        print(f"恢复初始 -> 当前关闭数: {len(mgr.closed_stations())}")