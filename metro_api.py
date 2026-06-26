"""
上海地铁 API 数据获取与处理模块
=================================

提供两个数据接口的请求封装：
  1. lineStations  — 获取线路站点列表
  2. fltime        — 获取首班车时间及站间运行间隔

使用方法
--------
  from metro_api import MetroAPI

  api = MetroAPI()

  # 获取站点
  stations = api.fetch_stations(1)    # 1 号线
  api.save_stations_csv(1, stations)  # 保存为 CSV

  # 获取站间运行时间
  intervals = api.fetch_fltime(1)
  api.save_fltime_csv(1, intervals)
"""

import csv
import json
import os
import subprocess
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

BASE_URL = "https://m.shmetro.com/interface/metromap/metromap.aspx"

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

CURL_HEADERS = [
    "-H", "Accept: application/json",
    "-H", "Content-Length: 0",
    "-H", "Origin: https://service.shmetro.com",
    "-H", "Referer: https://service.shmetro.com/",
    "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
]

LINE_NAMES = {
    1: "1号线", 2: "2号线", 3: "3号线", 4: "4号线", 5: "5号线",
    6: "6号线", 7: "7号线", 8: "8号线", 9: "9号线", 10: "10号线",
    11: "11号线", 12: "12号线", 13: "13号线", 14: "14号线", 15: "15号线",
    16: "16号线", 17: "17号线", 18: "18号线",
    41: "浦江线", 51: "市域机场线",
}

ALL_LINES = list(range(1, 19)) + [41, 51]

OUT_DIR = "metro_data"

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def safe_time(t: str) -> int | None:
    """将 'HH:MM' 字符串转为分钟数；无效值（'--' 等）返回 None。"""
    if not t or t == "--":
        return None
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except (ValueError, IndexError):
        return None


def _curl_post(url: str, timeout: int = 10) -> list | dict:
    """通过 curl POST 请求 API，返回解析后的 JSON 数据。

    在 Windows 上 urllib 有 SSL / GBK 问题，因此优先使用 curl 子进程。
    """
    cmd = ["curl", "-s", f"--max-time", str(timeout)] + CURL_HEADERS + ["-X", "POST", url]
    result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
    if result.returncode != 0 or not result.stdout:
        raise ConnectionError(f"curl 请求失败 (rc={result.returncode})")
    return json.loads(result.stdout.decode("utf-8"))


def _urllib_post(url: str, timeout: int = 10) -> list | dict:
    """通过 urllib POST 请求 API（备用方案）。"""
    req = urllib.request.Request(url, data=b"", headers=REQUEST_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_json(func: str, line: int, timeout: int = 10) -> list | dict:
    """请求 API，返回 JSON 数据。优先使用 curl，失败时回退到 urllib。"""
    params = urllib.parse.urlencode({"func": func, "line": line})
    url = f"{BASE_URL}?{params}"
    try:
        return _curl_post(url, timeout=timeout)
    except Exception:
        return _urllib_post(url, timeout=timeout)


# ---------------------------------------------------------------------------
# 1. 站点数据 (lineStations)
# ---------------------------------------------------------------------------


def parse_stations(raw: dict, line: int) -> list[dict]:
    """解析 lineStations 返回的 JSON，提取站点列表。

    返回 [{line, station_id, station_name}, ...]
    """
    locations = raw.get("levels", [{}])[0].get("locations", [])
    return [
        {"line": line, "station_id": loc["id"], "station_name": loc["title"]}
        for loc in locations
    ]


def fetch_stations(line: int) -> list[dict]:
    """获取指定线路的所有站点。"""
    raw = fetch_json("lineStations", line)
    return parse_stations(raw, line)


def save_stations_csv(line: int, stations: list[dict],
                      out_dir: str = OUT_DIR) -> str:
    """将站点列表保存为 CSV 文件，返回文件路径。"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"line-{line:02d}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["line", "station_id", "station_name"])
        writer.writeheader()
        writer.writerows(stations)
    return path


def fetch_all_stations(lines: list[int] | None = None,
                       out_dir: str = OUT_DIR) -> dict[int, list[dict]]:
    """批量获取所有线路的站点并保存 CSV。

    参数
    ----
    lines : list[int] | None
        线路列表，默认 ALL_LINES（1-18, 41, 51）
    out_dir : str
        输出目录

    返回 {line: stations_list}
    """
    if lines is None:
        lines = ALL_LINES
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for line in lines:
        stations = fetch_stations(line)
        path = save_stations_csv(line, stations, out_dir)
        name = LINE_NAMES.get(line, f"L{line}")
        print(f"{name:8s}(L{line:2d}): {len(stations):2d} stations -> {path}")
        results[line] = stations
    return results


# ---------------------------------------------------------------------------
# 2. 站间运行时间 (fltime)
# ---------------------------------------------------------------------------


def _dedup_ordered(entries: list[dict]) -> list[tuple[dict, int]]:
    """对同一方向的原始数据按 stat_id 去重，保留原始顺序。

    返回 [(entry_obj, time_minutes), ...]
    """
    seen = {}
    for e in entries:
        t = safe_time(e.get("first_time"))
        if t is None:
            continue
        sid = e["stat_id"]
        if sid not in seen:
            seen[sid] = (e, t)

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
    """从去重且有序的条目列表中计算站间运行时间。

    返回 [(line, direction, from_station, to_station, interval_min), ...]

    自动检测时间递增/递减趋势以确定列车运行方向。
    """
    if len(ordered) < 2:
        return []

    inc = sum(1 for i in range(1, len(ordered)) if ordered[i][1] > ordered[i - 1][1])
    dec = sum(1 for i in range(1, len(ordered)) if ordered[i][1] < ordered[i - 1][1])

    results = []
    if inc >= dec:
        # 物理站点顺序 = 列车运行方向（时间递增）
        for i in range(1, len(ordered)):
            diff = ordered[i][1] - ordered[i - 1][1]
            if 0 < diff < 60:
                results.append((
                    line, label,
                    ordered[i - 1][0]["name"],
                    ordered[i][0]["name"],
                    diff,
                ))
    else:
        # 列车运行方向与物理站点顺序相反（时间递减）
        # 从后往前处理，得到正确的运行方向
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
    """解析 fltime 返回的 JSON，提取站间运行时间。

    返回 [(line, direction, from_station, to_station, interval_min), ...]
    """
    # 按 direction 分组
    dir_groups: dict[int, list[dict]] = {}
    for e in raw:
        d = e.get("direction")
        if d is None:
            continue
        dir_groups.setdefault(d, []).append(e)

    all_intervals = []
    for d_val in sorted(dir_groups.keys()):
        entries = dir_groups[d_val]
        label = entries[0].get("description", f"dir_{d_val}")
        ordered = _dedup_ordered(entries)
        intervals = calc_intervals(ordered, label, line)
        all_intervals.extend(intervals)

    return all_intervals


def fetch_fltime(line: int) -> list[tuple]:
    """获取指定线路的站间运行时间。"""
    raw = fetch_json("fltime", line)
    return parse_fltime(raw, line)


def save_fltime_csv(line: int, intervals: list[tuple],
                    out_dir: str = OUT_DIR) -> str:
    """将站间运行时间保存为 CSV 文件，返回文件路径。"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"fltime-{line:02d}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["line", "direction", "from_station", "to_station", "interval_min"])
        writer.writerows(intervals)
    return path


def fetch_all_fltime(lines: list[int] | None = None,
                     out_dir: str = OUT_DIR) -> dict[int, list[tuple]]:
    """批量获取所有线路的站间运行时间并保存 CSV。

    参数
    ----
    lines : list[int] | None
        线路列表，默认 ALL_LINES（1-18, 41, 51）
    out_dir : str
        输出目录

    返回 {line: intervals_list}
    """
    if lines is None:
        lines = ALL_LINES
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for line in lines:
        intervals = fetch_fltime(line)
        path = save_fltime_csv(line, intervals, out_dir)
        name = LINE_NAMES.get(line, f"L{line}")
        print(f"{name:8s}(L{line:2d}): {len(intervals):2d} intervals -> {path}")
        results[line] = intervals
    return results


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("  上海地铁数据采集")
    print("=" * 50)

    # 1. 获取所有站点
    print("\n--- 站点数据 (lineStations) ---")
    stations = fetch_all_stations()
    total_stations = sum(len(v) for v in stations.values())
    print(f"\n共 {total_stations} 个站点")

    # 2. 获取所有站间运行时间
    print("\n--- 站间运行时间 (fltime) ---")
    intervals = fetch_all_fltime()
    total_intervals = sum(len(v) for v in intervals.values())
    print(f"\n共 {total_intervals} 个站间区间")

    print(f"\n所有文件已保存到 {OUT_DIR}/ 目录")