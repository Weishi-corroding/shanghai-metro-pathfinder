"""
上海地铁数据采集 — 独立爬取脚本
================================

从上海地铁官方移动端接口 (m.shmetro.com) 获取线路站点和站间运行时间，
并以结构化 CSV 格式保存到本地。

功能：
  1. 获取指定线路的站点列表      → metro_data/line-XX.csv
  2. 获取指定线路的站间运行时间  → metro_data/fltime-XX.csv

数据来源：
  https://m.shmetro.com/interface/metromap/metromap.aspx
  两个接口：
    - func=lineStations  — 获取线路所有站点的 ID 和名称
    - func=fltime        — 获取各方向首班车时刻，用于推算站间运行时间

CSV 输出格式：

  line-XX.csv（站点列表）：
    line,station_id,station_name
    1,station0111,莘庄
    1,station0112,外环路
    ...

  fltime-XX.csv（站间运行时间）：
    line,direction,from_station,to_station,interval_min
    1,往富锦路,莘庄,外环路,3
    1,往富锦路,外环路,莲花路,2
    ...

运行方式：
  python request_metro.py                  # 获取全部 20 条线路（站点 + 运行时间）
  python request_metro.py --stations       # 仅获取站点
  python request_metro.py --fltime         # 仅获取运行时间
  python request_metro.py 1 2 3            # 仅获取指定线路

依赖：
  仅使用 Python 标准库（json, csv, os, subprocess, urllib）。
  优先使用 curl 子进程发请求（Windows 上 urllib 有 SSL/GBK 兼容问题），
  失败时自动回退到 urllib。

作者：weishi
日期：2026-06-26
"""

import csv
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request


# ==============================================================================
# 常量配置
# ==============================================================================

# 上海地铁官方移动端 API 地址
BASE_URL = "https://m.shmetro.com/interface/metromap/metromap.aspx"

# urllib 使用的 HTTP 请求头 — 伪装成浏览器访问
REQUEST_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Length": "0",
    "Origin": "https://service.shmetro.com",
    "Referer": "https://service.shmetro.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
    ),
}

# curl 子进程使用的等价请求头（列表格式，供 subprocess.run 拼接）
CURL_HEADERS = [
    "-H", "Accept: application/json",
    "-H", "Content-Length: 0",
    "-H", "Origin: https://service.shmetro.com",
    "-H", "Referer: https://service.shmetro.com/",
    "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
]

# 线路编号 → 中文名称映射（上海地铁共 20 条线路：1-18 号线 + 浦江线 + 市域机场线）
LINE_NAMES = {
    1: "1号线", 2: "2号线", 3: "3号线", 4: "4号线", 5: "5号线",
    6: "6号线", 7: "7号线", 8: "8号线", 9: "9号线", 10: "10号线",
    11: "11号线", 12: "12号线", 13: "13号线", 14: "14号线", 15: "15号线",
    16: "16号线", 17: "17号线", 18: "18号线",
    41: "浦江线", 51: "市域机场线",
}

# 全部线路的编号列表（1-18 常规线路 + 41 浦江线 + 51 市域机场线）
ALL_LINES = list(range(1, 19)) + [41, 51]

# 原始 CSV 输出目录
OUT_DIR = "metro_data"


# ==============================================================================
# 工具函数
# ==============================================================================

def safe_time(t: str) -> int | None:
    """将 'HH:MM' 格式的时间字符串转换为从零点开始的分钟数。

    用于处理 fltime 接口返回的 first_time 字段。
    如果时间不可解析（如 '--' 或空字符串），返回 None。

    示例：
        safe_time("06:30") → 390
        safe_time("--")    → None
    """
    if not t or t == "--":
        return None
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except (ValueError, IndexError):
        return None


def _curl_post(url: str, timeout: int = 10) -> list | dict:
    """通过 curl 子进程向 API 发送 POST 请求，返回解析后的 JSON。

    为什么优先使用 curl？
    - Windows 上 Python 的 urllib 在处理某些 SSL 证书时会卡死
    - 地铁 API 返回的 GBK 编码内容在 urllib 中可能乱码
    - curl 作为外部进程更可靠；几乎所有系统都预装了 curl

    参数：
        url     — 完整的 API URL（含查询参数）
        timeout — curl 最大等待秒数

    返回：解析后的 JSON 数据（list 或 dict）

    异常：
        ConnectionError — curl 返回非零退出码或无输出时抛出
    """
    cmd = ["curl", "-s", f"--max-time", str(timeout)] + CURL_HEADERS + ["-X", "POST", url]
    result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
    if result.returncode != 0 or not result.stdout:
        raise ConnectionError(f"curl 请求失败 (rc={result.returncode})")
    return json.loads(result.stdout.decode("utf-8"))


def _urllib_post(url: str, timeout: int = 10) -> list | dict:
    """通过 urllib 向 API 发送 POST 请求，返回解析后的 JSON。

    作为 curl 不可用时的备用方案。使用空 body 的 POST 请求。

    参数：
        url     — 完整的 API URL（含查询参数）
        timeout — 连接超时秒数
    """
    req = urllib.request.Request(url, data=b"", headers=REQUEST_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_json(func: str, line: int, timeout: int = 10) -> list | dict:
    """请求上海地铁 API，返回 JSON 数据。

    这是所有 API 请求的统一入口。自动选择传输方式：
    1. 优先使用 curl（可靠但需要系统安装 curl）
    2. curl 失败时回退到 urllib（纯 Python，无需外部依赖）

    参数：
        func    — API 功能名：'lineStations'（站点）或 'fltime'（运行时间）
        line    — 线路编号，如 1 表示 1 号线，41 表示浦江线
        timeout — 超时秒数，默认 10

    返回：解析后的 JSON（list 或 dict，取决于接口）
    """
    params = urllib.parse.urlencode({"func": func, "line": line})
    url = f"{BASE_URL}?{params}"
    try:
        return _curl_post(url, timeout=timeout)
    except Exception:
        # curl 不可用时回退到 urllib
        return _urllib_post(url, timeout=timeout)


# ==============================================================================
# 1. 站点数据（lineStations 接口）
# ==============================================================================

def parse_stations(raw: dict, line: int) -> list[dict]:
    """解析 lineStations API 返回的 JSON，提取站点列表。

    API 返回的数据结构大致为：
    {
      "levels": [
        {
          "locations": [
            {"id": "station0111", "title": "莘庄"},
            {"id": "station0112", "title": "外环路"},
            ...
          ]
        }
      ]
    }

    参数：
        raw  — API 返回的原始 JSON dict
        line — 线路编号

    返回：
        [{"line": 1, "station_id": "station0111", "station_name": "莘庄"}, ...]
        每个元素包含线路编号、API 原始站点 ID 和站点中文名称
    """
    # levels[0] 是第一个（通常也是唯一的）层级
    locations = raw.get("levels", [{}])[0].get("locations", [])
    return [
        {"line": line, "station_id": loc["id"], "station_name": loc["title"]}
        for loc in locations
    ]


def fetch_stations(line: int) -> list[dict]:
    """从 API 获取指定线路的所有站点。

    返回：站点列表，每个站点为 dict，含 line / station_id / station_name 三个字段。
    """
    raw = fetch_json("lineStations", line)
    return parse_stations(raw, line)


def save_stations_csv(line: int, stations: list[dict],
                      out_dir: str = OUT_DIR) -> str:
    """将站点列表保存为 UTF-8 BOM 编码的 CSV 文件。

    文件名格式：line-{线路编号:02d}.csv（如 line-01.csv）

    使用 UTF-8 BOM (utf-8-sig) 编码以兼容 Excel 直接打开中文 CSV。

    参数：
        line     — 线路编号
        stations — 站点数据列表
        out_dir  — 输出目录

    返回：写入的文件路径
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"line-{line:02d}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["line", "station_id", "station_name"])
        writer.writeheader()
        writer.writerows(stations)
    return path


# ==============================================================================
# 2. 站间运行时间（fltime 接口）
# ==============================================================================

def _dedup_ordered(entries: list[dict]) -> list[tuple[dict, int]]:
    """对同一方向的 fltime 原始条目按 stat_id 去重，保留首次出现顺序。

    fltime 接口可能对同一站点返回多条记录（不同列车类型等）。
    我们只需要每个站点的首班车时间，因此取首次出现的有效记录。

    参数：
        entries — 同一 direction 下的原始条目列表，
                  每条含 stat_id（站点ID）、first_time（首班车时间）、
                  name（站点名称）

    返回：
        [(entry_dict, time_minutes), ...]
        每个元素为 (原始条目, 首班车时间分钟数)
        已去重，顺序与原列表中的首次出现顺序一致
    """
    # 第一遍：记录每个 stat_id 首次出现的有效时间和条目
    seen = {}
    for e in entries:
        t = safe_time(e.get("first_time"))
        if t is None:          # 跳过无法解析的时间（如 '--'）
            continue
        sid = e["stat_id"]
        if sid not in seen:
            seen[sid] = (e, t)

    # 第二遍：按原始顺序输出，每个 stat_id 只输出一次
    ordered = []
    seen_ids = set()
    for e in entries:
        sid = e["stat_id"]
        if sid in seen and sid not in seen_ids:
            ordered.append(seen[sid])
            seen_ids.add(sid)
    return ordered


def calc_intervals(ordered: list[tuple[dict, int]],
                   label: str, line: int) -> list[tuple]:
    """从有序的首班车时间列表推算相邻站间的列车运行分钟数。

    核心思路：
    - API 不直接返回站间运行时间，而是返回各站首班车到达时刻
    - 相邻两站的首班车时间差 ≈ 该区间的列车行驶时间
    - 根据时间递增/递减趋势自动判断列车运行方向

    参数：
        ordered — _dedup_ordered() 的输出，已去重且按原始顺序排列
        label   — 方向描述文字，如 '往富锦路'、'全程（内）'
        line    — 线路编号

    返回：
        [(line, direction, from_station, to_station, interval_min), ...]
        每个元素为一个区间的 (线路, 方向, 起点站名, 终点站名, 分钟数)

    特殊情况处理：
        - 少于 2 个站点：无法计算区间，返回空列表
        - 时间差超出 (0, 60) 分钟：视为异常数据（如跨日），自动过滤
        - 时间递减序列：说明列车运行方向与站点排列方向相反，
          自动反转区间方向
    """
    if len(ordered) < 2:
        return []

    # 统计时间递增和递减的对数，判断整体趋势
    inc = sum(1 for i in range(1, len(ordered))
              if ordered[i][1] > ordered[i - 1][1])
    dec = sum(1 for i in range(1, len(ordered))
              if ordered[i][1] < ordered[i - 1][1])

    results = []
    if inc >= dec:
        # 递增趋势：时间越晚的站排在越后面，运行方向 = 站点排列方向
        for i in range(1, len(ordered)):
            diff = ordered[i][1] - ordered[i - 1][1]
            if 0 < diff < 60:   # 过滤异常值（≤0 或 ≥60 分钟都不合理）
                results.append((
                    line, label,
                    ordered[i - 1][0]["name"],
                    ordered[i][0]["name"],
                    diff,
                ))
    else:
        # 递减趋势：时间越早的站排在越后面，运行方向 = 站点排列反方向
        # 从后往前遍历，使区间方向与列车运行方向一致
        for i in range(len(ordered) - 1, 0, -1):
            diff = ordered[i - 1][1] - ordered[i][1]
            if 0 < diff < 60:
                results.append((
                    line, label,
                    ordered[i][0]["name"],
                    ordered[i - 1][0]["name"],
                    diff,
                ))
    return results


def parse_fltime(raw: list | dict, line: int) -> list[tuple]:
    """解析 fltime API 返回的 JSON，提取各方向站间运行时间。

    API 返回一个列表，每个元素代表一个站点在一个方向上的首班车信息，
    包含 direction 字段区分上下行。先按 direction 分组，再分别计算区间。

    参数：
        raw  — API 返回的原始 JSON（一个 list）
        line — 线路编号

    返回：
        [(line, direction, from_station, to_station, interval_min), ...]
        所有方向合并后的区间列表
    """
    # 按 direction 字段分组（direction 是整数，如 1 表示上行、2 表示下行）
    dir_groups: dict[int, list[dict]] = {}
    for e in raw:
        d = e.get("direction")
        if d is None:
            continue
        # setdefault: 如果 key 不存在则创建空列表，然后 append
        dir_groups.setdefault(d, []).append(e)

    all_intervals = []
    for d_val in sorted(dir_groups.keys()):
        entries = dir_groups[d_val]
        # 取第一个条目的 description 字段作为方向标签（如 '往富锦路'）
        label = entries[0].get("description", f"dir_{d_val}")
        ordered = _dedup_ordered(entries)
        intervals = calc_intervals(ordered, label, line)
        all_intervals.extend(intervals)

    return all_intervals


def fetch_fltime(line: int) -> list[tuple]:
    """从 API 获取指定线路的站间运行时间。

    返回：区间列表，每个元素为 (line, direction, from, to, minutes)。
    """
    raw = fetch_json("fltime", line)
    return parse_fltime(raw, line)


def save_fltime_csv(line: int, intervals: list[tuple],
                    out_dir: str = OUT_DIR) -> str:
    """将站间运行时间保存为 UTF-8 BOM 编码的 CSV 文件。

    文件名格式：fltime-{线路编号:02d}.csv（如 fltime-01.csv）

    参数：
        line      — 线路编号
        intervals — 区间数据列表
        out_dir   — 输出目录

    返回：写入的文件路径
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"fltime-{line:02d}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["line", "direction", "from_station", "to_station", "interval_min"])
        writer.writerows(intervals)
    return path


# ==============================================================================
# 主入口 — 命令行解析 + 批量采集
# ==============================================================================

def main():
    """解析命令行参数并执行数据采集。

    命令行参数规则：
      --stations         仅获取站点（跳过运行时间）
      --fltime           仅获取运行时间（跳过站点）
      <数字> <数字> ...   指定线路编号（如 1 2 3），默认全部 20 条线路

    示例：
      python request_metro.py                  # 全量采集
      python request_metro.py --stations       # 只爬站点
      python request_metro.py --fltime         # 只爬运行时间
      python request_metro.py 1 2 3            # 只爬 1/2/3 号线
      python request_metro.py --stations 1 2   # 只爬 1/2 号线的站点
    """
    # ---- 解析命令行 ----
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    # 默认两项都做；遇到 --stations / --fltime 则只做对应的
    do_stations = True
    do_fltime = True
    if "--stations" in flags:
        do_fltime = False
    if "--fltime" in flags:
        do_stations = False

    # 如果提供了数字参数则只处理指定线路，否则处理全部 20 条
    lines = [int(a) for a in args if a.lstrip("-").isdigit()] if args else ALL_LINES

    # ---- 打印概览 ----
    show_lines = ", ".join(f"{LINE_NAMES.get(l, f'L{l}')}({l})" for l in lines)
    print("=" * 56)
    print("  上海地铁数据采集")
    print("=" * 56)
    print(f"  线路: {show_lines}")
    print(f"  目录: {OUT_DIR}/")
    print(f"  内容: {'站点' if do_stations else ''}"
          f"{' + ' if do_stations and do_fltime else ''}"
          f"{'运行时间' if do_fltime else ''}")
    print()

    try:
        # ---- 第 1 步：获取站点列表 ----
        if do_stations:
            print("--- [1/2] 站点数据 (lineStations) ---")
            os.makedirs(OUT_DIR, exist_ok=True)
            total_stations = 0
            for line in lines:
                stations = fetch_stations(line)
                path = save_stations_csv(line, stations, OUT_DIR)
                name = LINE_NAMES.get(line, f"L{line}")
                print(f"  {name:8s}(L{line:2d}): {len(stations):2d} stations -> {path}")
                total_stations += len(stations)
            print(f"  => 共 {total_stations} 个站点\n")

        # ---- 第 2 步：获取站间运行时间 ----
        if do_fltime:
            print("--- [2/2] 站间运行时间 (fltime) ---")
            os.makedirs(OUT_DIR, exist_ok=True)
            total_intervals = 0
            for line in lines:
                intervals = fetch_fltime(line)
                path = save_fltime_csv(line, intervals, OUT_DIR)
                name = LINE_NAMES.get(line, f"L{line}")
                print(f"  {name:8s}(L{line:2d}): {len(intervals):2d} intervals -> {path}")
                total_intervals += len(intervals)
            print(f"  => 共 {total_intervals} 个站间区间\n")

        print("完成！所有文件已保存到 metro_data/ 目录")

    except Exception as e:
        # 网络错误、JSON 解析失败等统一在此处理
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
