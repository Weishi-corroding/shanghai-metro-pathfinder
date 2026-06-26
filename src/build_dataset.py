"""
build_dataset.py — 数据集构建脚本
==================================

从 metro_data/ 下的原始抓取数据生成课设要求的规范数据集：

输入：
  metro_data/line-XX.csv     # 各线路站点（line, station_id, station_name）
  metro_data/fltime-XX.csv   # 各线路站间运行时间

输出：
  data/Station.csv           # 全网站点表（站点ID, 站点名称, 所属线路, 运营状态）
  data/Station_init.csv      # Station.csv 初始备份（用于"恢复初始状态"）
  data/Edge.csv              # 图边表（起点ID, 终点ID, 线路, 方向, 时间）
  data/update_station_status.csv  # 批量状态更新示例文件

关键决策：
  1. 同名换乘站按线路拆分为独立节点（人民广场拆为3个：1/2/8号线各一）
  2. 站点ID格式：LLNN（线路号前缀+本线内顺序号，0填充至 4 位）
  3. 换乘边：同名跨线站点两两互连，line="换乘"，time=5
  4. 区间边为有向边（上下行运行时间可能不同）
  5. 4号线 direction 字段保留"全程（内）"/"全程（外）"用于内外圈标记
  6. 站名清洗：去除尾部空格

运行：
  python -m src.build_dataset
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "metro_data"
OUT_DIR = ROOT / "data"

ALL_LINES = list(range(1, 19)) + [41, 51]

# 换乘边耗时（分钟）
TRANSFER_TIME = 5

# 线路号到中文名（用于 Station.csv 的"所属线路"字段）
LINE_NAMES = {
    1: "1号线", 2: "2号线", 3: "3号线", 4: "4号线", 5: "5号线",
    6: "6号线", 7: "7号线", 8: "8号线", 9: "9号线", 10: "10号线",
    11: "11号线", 12: "12号线", 13: "13号线", 14: "14号线", 15: "15号线",
    16: "16号线", 17: "17号线", 18: "18号线",
    41: "浦江线", 51: "市域机场线",
}


# ---------------------------------------------------------------------------
# 数据清洗辅助
# ---------------------------------------------------------------------------

def clean_name(name: str) -> str:
    """去除站名首尾空格。"""
    return name.strip()


def line_str(line_num: int) -> str:
    """线路号 -> 中文名（带容错）。"""
    return LINE_NAMES.get(line_num, f"{line_num}号线")


# ---------------------------------------------------------------------------
# 1. 站点数据构建
# ---------------------------------------------------------------------------

def build_stations() -> tuple[list[dict], dict[tuple[int, str], str]]:
    """从 line-XX.csv 构建全网站点表。

    返回:
      stations: 站点字典列表（含 station_id, station_name, line, status）
      name_index: {(line, station_name): station_id} 用于 fltime 解析时反查
    """
    stations: list[dict] = []
    name_index: dict[tuple[int, str], str] = {}

    for line_num in ALL_LINES:
        path = RAW_DIR / f"line-{line_num:02d}.csv"
        with open(path, encoding="utf-8-sig") as f:
            seen_names: set[str] = set()
            seq = 1
            for row in csv.DictReader(f):
                name = clean_name(row["station_name"])
                # 防御性去重：同一线路文件内若有重复站名，跳过
                if name in seen_names:
                    continue
                seen_names.add(name)

                # 站点ID格式：LLNN（线路号 2 位 + 本线序号 2 位）
                # 浦江线 41、机场线 51 沿用相同规则
                station_id = f"{line_num:02d}{seq:02d}"

                stations.append({
                    "station_id": station_id,
                    "station_name": name,
                    "line": line_str(line_num),
                    "line_num": line_num,
                    "status": "开启",
                })
                name_index[(line_num, name)] = station_id
                seq += 1

    return stations, name_index


# ---------------------------------------------------------------------------
# 2. 边数据构建
# ---------------------------------------------------------------------------

def build_interval_edges(name_index: dict[tuple[int, str], str]) -> list[dict]:
    """从 fltime-XX.csv 构建区间边（有向，按 direction 区分上下行）。"""
    edges: list[dict] = []
    missing: list[str] = []

    for line_num in ALL_LINES:
        path = RAW_DIR / f"fltime-{line_num:02d}.csv"
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                from_name = clean_name(row["from_station"])
                to_name = clean_name(row["to_station"])
                direction = row["direction"]
                time_min = int(row["interval_min"])

                # 反查站点ID
                from_id = name_index.get((line_num, from_name))
                to_id = name_index.get((line_num, to_name))

                if from_id is None or to_id is None:
                    missing.append(
                        f"L{line_num} {from_name}({from_id}) -> {to_name}({to_id})"
                    )
                    continue

                edges.append({
                    "from_id": from_id,
                    "to_id": to_id,
                    "line": line_str(line_num),
                    "direction": direction,
                    "time": time_min,
                })

    if missing:
        print(f"[WARN] 反查失败的边: {len(missing)} 条")
        for m in missing[:5]:
            print(f"    {m}")
        if len(missing) > 5:
            print(f"    ... 还有 {len(missing) - 5} 条")

    return edges


# ---------------------------------------------------------------------------
# 2.5 补全线内缺失的邻接站边
# ---------------------------------------------------------------------------


def fill_missing_adjacent_edges(
    stations: list[dict],
    edges: list[dict],
) -> list[dict]:
    """补全线内缺失的邻接站边。

    由于 fltime 仅提供首班车时间，某些中继站之间的边可能缺失
    （例：1 号线锦江乐园→上海南站属于不同首班车段）。
    对每条线扫描连续站序，缺边时用反向边的时间补全。

    返回补全后的边列表。
    """
    line_order: dict[int, list[dict]] = defaultdict(list)
    for s in stations:
        line_order[s["line_num"]].append(s)
    for ln in line_order:
        line_order[ln].sort(key=lambda x: int(x["station_id"]))

    existing: set[tuple[str, str]] = {(e["from_id"], e["to_id"]) for e in edges}
    rev_time: dict[tuple[str, str], int] = {}
    for e in edges:
        rev_time[(e["to_id"], e["from_id"])] = e["time"]

    filled = list(edges)
    added = 0

    for ln, stns in line_order.items():
        line_name = stns[0]["line"]
        for i in range(len(stns) - 1):
            a, b = stns[i]["station_id"], stns[i + 1]["station_id"]

            # 尝试用反向边时间补全
            for fwd, rev in [(a, b), (b, a)]:
                if (fwd, rev) in existing:
                    continue
                mt = rev_time.get((fwd, rev))
                if mt is not None:
                    filled.append({
                        "from_id": fwd, "to_id": rev,
                        "line": line_name, "direction": "", "time": mt,
                    })
                    added += 1
                    existing.add((fwd, rev))

            # 如果正反向都缺失（如 Y 字型分支的分叉点），用默认值 3 分钟
            if (a, b) not in existing and (b, a) not in existing:
                for fwd, rev in [(a, b), (b, a)]:
                    filled.append({
                        "from_id": fwd, "to_id": rev,
                        "line": line_name, "direction": "", "time": 3,
                    })
                    added += 1
                    existing.add((fwd, rev))

    if added:
        print(f"[补全] 新增 {added} 条缺失的邻接边")
    return filled


def build_transfer_edges(stations: list[dict]) -> list[dict]:
    """根据同名跨线站点构建换乘边。

    同名站点两两互连，time=5，line="换乘"，direction 留空。
    """
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for s in stations:
        name_to_ids[s["station_name"]].append(s["station_id"])

    edges: list[dict] = []
    for name, ids in name_to_ids.items():
        if len(ids) < 2:
            continue
        # 同名站两两互连（双向，所以用所有有序对）
        for i in ids:
            for j in ids:
                if i == j:
                    continue
                edges.append({
                    "from_id": i,
                    "to_id": j,
                    "line": "换乘",
                    "direction": "",
                    "time": TRANSFER_TIME,
                })

    return edges


# ---------------------------------------------------------------------------
# 3. CSV 输出
# ---------------------------------------------------------------------------

def write_station_csv(stations: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["站点ID", "站点名称", "所属线路", "运营状态"])
        for s in stations:
            writer.writerow([s["station_id"], s["station_name"], s["line"], s["status"]])


def write_edge_csv(edges: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["起点站ID", "终点站ID", "线路", "运行方向", "通行时间"])
        for e in edges:
            writer.writerow([e["from_id"], e["to_id"], e["line"], e["direction"], e["time"]])


def write_update_status_example(path: Path) -> None:
    """生成批量更新示例文件（含一些用于测试的关闭指令）。"""
    rows = [
        ("漕宝路", "1号线", "关闭"),
        ("陆家嘴", "2号线", "关闭"),
        ("萧塘", "5号线", "开启"),
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["站点名称", "所属线路", "运营状态"])
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# 4. 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print(" build_dataset — 构建规范数据集")
    print("=" * 56)

    # 1. 构建站点
    stations, name_index = build_stations()
    print(f"\n[1/3] 站点构建完成: {len(stations)} 个站点")

    # 按线路统计
    by_line: dict[int, int] = defaultdict(int)
    for s in stations:
        by_line[s["line_num"]] += 1
    for n in ALL_LINES:
        print(f"      {line_str(n):8s}(L{n:2d}): {by_line[n]:3d} 站")

    # 换乘站统计
    name_count: dict[str, int] = defaultdict(int)
    for s in stations:
        name_count[s["station_name"]] += 1
    transfer_count = sum(1 for c in name_count.values() if c >= 2)
    print(f"\n      跨线换乘站（不同物理站）: {transfer_count} 个")

    # 2. 构建边
    interval_edges = build_interval_edges(name_index)
    print(f"\n[2/3] 区间边构建完成: {len(interval_edges)} 条")

    # 2.5 补全缺失的邻接边
    filled_edges = fill_missing_adjacent_edges(stations, interval_edges)
    print(f"      补全后区间边: {len(filled_edges)} 条")

    transfer_edges = build_transfer_edges(stations)
    print(f"      换乘边构建完成: {len(transfer_edges)} 条")

    all_edges = filled_edges + transfer_edges
    print(f"      总边数: {len(all_edges)} 条")

    # 3. 写出
    station_csv = OUT_DIR / "Station.csv"
    station_init_csv = OUT_DIR / "Station_init.csv"
    edge_csv = OUT_DIR / "Edge.csv"
    update_csv = OUT_DIR / "update_station_status.csv"

    write_station_csv(stations, station_csv)
    write_station_csv(stations, station_init_csv)
    write_edge_csv(all_edges, edge_csv)
    write_update_status_example(update_csv)

    print(f"\n[3/3] 文件输出:")
    print(f"      {station_csv}")
    print(f"      {station_init_csv}")
    print(f"      {edge_csv}")
    print(f"      {update_csv}")

    # 验证：与课设要求基准对比（525 站点、1226 边）
    print("\n=== 与课设要求基准对比 ===")
    print(f"  站点数:  {len(stations):4d}  (课设基准: 525)")
    print(f"  边数:    {len(all_edges):4d}  (课设基准: 1226)")

    if abs(len(stations) - 525) > 5 or abs(len(all_edges) - 1226) > 50:
        print("  [WARN] 数据规模与基准偏差较大，请检查抓取数据完整性")
    else:
        print("  [OK] 数据规模符合预期")


if __name__ == "__main__":
    main()