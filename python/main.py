"""
上海地铁路径规划与运营管理系统 — 主入口
=========================================

启动方式：
  python main.py

系统功能：
  1. 线路站点信息/运营状态管理（M2）
  2. 所需时间最短路径规划（M3）
  3. 所需换乘次数最少路径规划（M4）
  4. 退出系统

数据文件位于 data/ 目录：
  - Station.csv       全网站点表（含运营状态）
  - Edge.csv          图边表（含换乘边）
  - Station_init.csv  初始状态备份（恢复用）
  - update_station_status.csv  批量更新示例
"""

import sys
import os

# 确保能导入 src 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from graph import Graph
from station import StationManager
from menu import MetroMenu


def main() -> None:
    # 1. 加载图数据
    print("正在加载图数据...", end=" ")
    graph = Graph()
    graph.load()
    print(f"{graph.node_count} 节点, {graph.edge_count} 条边")

    # 2. 加载站点数据
    print("正在加载站点数据...", end=" ")
    station_mgr = StationManager()
    station_mgr.load()
    print(f"{len(station_mgr)} 个站点")

    # 3. 检查数据完整性
    closed = station_mgr.closed_stations()
    if closed:
        print(f"  当前有 {len(closed)} 个站点处于关闭状态")

    # 4. 启动菜单
    menu = MetroMenu(station_mgr, graph)
    menu.main_loop()


if __name__ == "__main__":
    main()