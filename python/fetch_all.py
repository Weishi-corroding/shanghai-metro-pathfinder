"""
上海地铁数据采集 — 一键运行脚本
================================

从上海地铁官方接口批量获取数据并保存为 CSV。

获取的数据：
  1. metro_data/line-*.csv          — 每条线路的站点列表
  2. metro_data/fltime-*.csv        — 每条线路的站间运行时间（分钟）

运行方式：
  python fetch_all.py               # 获取全部 20 条线路
  python fetch_all.py --stations    # 仅获取站点
  python fetch_all.py --fltime      # 仅获取运行时间
  python fetch_all.py --lines 1 2   # 仅获取指定线路
"""

import sys

from metro_api import (
    LINE_NAMES,
    ALL_LINES,
    fetch_all_stations,
    fetch_all_fltime,
)


def main():
    # 解析命令行参数
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    do_stations = True
    do_fltime = True

    if "--stations" in flags:
        do_fltime = False
    if "--fltime" in flags:
        do_stations = False

    lines = [int(a) for a in args if a.lstrip("-").isdigit()] if args else ALL_LINES

    # 显示概览
    show_lines = ", ".join(f"{LINE_NAMES.get(l, f'L{l}')}({l})" for l in lines)
    print("=" * 56)
    print("  上海地铁数据采集工具")
    print("=" * 56)
    print(f"  线路: {show_lines}")
    print(f"  目录: metro_data/")
    print()

    try:
        if do_stations:
            print("--- [1/2] 站点数据 (lineStations) ---")
            stations = fetch_all_stations(lines)
            total = sum(len(v) for v in stations.values())
            print(f"  -> 共 {total} 个站点\n")

        if do_fltime:
            print("--- [2/2] 站间运行时间 (fltime) ---")
            intervals = fetch_all_fltime(lines)
            total = sum(len(v) for v in intervals.values())
            print(f"  -> 共 {total} 个站间区间\n")

        print("完成！所有文件已保存到 metro_data/ 目录")
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()