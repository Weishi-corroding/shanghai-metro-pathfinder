"""
menu.py — 多级控制台菜单交互（M1 模块）
========================================

菜单结构：
  主菜单 → 子菜单 1（线路/状态管理）
         → 子菜单 2（最短时间路径）
         → 子菜单 3（最少换乘路径）
         → 退出
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from station import StationManager
    from graph import Graph

from pathfinder import (
    dijkstra_shortest_time,
    dijkstra_min_transfers,
    yen_k_shortest_time,
    yen_k_min_transfers,
    format_path,
)
from utils import (
    read_menu_choice,
    read_yes_no,
    read_int,
    fuzzy_select_station,
    read_start_end_station,
    print_path_header,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

class MetroMenu:
    """控制台菜单主控类。持有 StationManager 和 Graph 实例。"""

    def __init__(self, station_mgr: StationManager, graph: Graph) -> None:
        self.station_mgr = station_mgr
        self.graph = graph

    # ==================== 主菜单 ====================

    def main_loop(self) -> None:
        """主菜单循环。只有选"4. 退出系统"才返回。"""
        while True:
            print()
            print("=" * 46)
            print("  上海地铁路径规划与运营管理系统")
            print("=" * 46)
            print("1. 线路站点信息/运营状态管理")
            print("2. 所需时间最短路径规划")
            print("3. 所需换乘次数最少路径规划")
            print("4. 退出系统")

            choice = read_menu_choice("请输入选项编号: ", 1, 4)

            if choice == 1:
                self.sub_menu_status()
            elif choice == 2:
                self.sub_menu_shortest_time()
            elif choice == 3:
                self.sub_menu_min_transfers()
            elif choice == 4:
                print("感谢使用！再见！")
                break

    # ==================== 子菜单 1: 线路/状态管理 ====================

    def sub_menu_status(self) -> None:
        """线路站点信息/运营状态管理二级菜单。"""
        while True:
            print()
            print("-- 线路站点信息/运营状态管理 --")
            print("1. 从 CSV 文件批量更新站点开启/关闭状态")
            print("2. 手工更新站点开启/关闭状态")
            print("3. 显示当前关闭站点")
            print("4. 恢复所有站点初始状态")
            print("5. 显示线路站点信息")
            print("6. 受关闭站点影响分析")
            print("7. 返回上级菜单")

            choice = read_menu_choice("请输入选项编号: ", 1, 7)

            if choice == 1:
                self._batch_update()
            elif choice == 2:
                self._manual_update()
            elif choice == 3:
                self._show_closed()
            elif choice == 4:
                self._restore_initial()
            elif choice == 5:
                self._show_line_info()
            elif choice == 6:
                self._affected_analysis()
            elif choice == 7:
                break

    def _batch_update(self) -> None:
        """M2-1: 从 CSV 批量更新站点状态。"""
        path = DATA_DIR / "update_station_status.csv"
        if not path.exists():
            print(f"更新文件不存在: {path}")
            return

        stats = self.station_mgr.batch_update_from_csv(path)
        if stats.get("errors"):
            for e in stats["errors"]:
                print(f"  {e}")
            return
        print(f"批量更新完成:")
        print(f"  更新: {stats['updated']} 条")
        if stats['not_found']:
            print(f"  未匹配: {stats['not_found']} 条")
        if stats['invalid']:
            print(f"  非法状态: {stats['invalid']} 条")
        self.station_mgr.save()

    def _manual_update(self) -> None:
        """M2-2: 手工更新站点状态。"""
        updated = 0
        modifiable = [
            s for s in self.station_mgr.all_stations()
            if s.line != "换乘"
        ]
        if not modifiable:
            print("当前无可操作站点。")
            return

        print("请输入待修改站点关键词（exit 退出）：")
        while True:
            keyword = input("> ").strip()
            if keyword.lower() in ("exit", "quit", "q"):
                break

            if not keyword:
                continue

            candidates = self.station_mgr.find_fuzzy(keyword)
            if not candidates:
                # 精确匹配
                exact = self.station_mgr.find_by_name(keyword)
                if not exact:
                    print("未匹配到对应站点，请重新输入。")
                    continue
                candidates = exact

            # 过滤只留可修改的
            candidates = [s for s in candidates
                          if any(s.station_id == ms.station_id for ms in modifiable)]

            if len(candidates) == 0:
                print("未匹配到对应站点，请重新输入。")
                continue

            if len(candidates) == 1:
                sel = candidates[0]
            else:
                print("匹配的站点如下：")
                for i, s in enumerate(candidates, 1):
                    print(f"  {i}. {s.name}（{s.line}）")
                try:
                    idx = int(input("请输入对应编号选择站点: ").strip())
                    if idx < 1 or idx > len(candidates):
                        print("编号无效。")
                        continue
                    sel = candidates[idx - 1]
                except ValueError:
                    print("输入无效。")
                    continue

            print(f"{sel.name},{sel.line},{sel.status}")
            new_status = input("请输入站点状态（开启/关闭）: ").strip()
            if new_status not in ("开启", "关闭"):
                print('状态值非法，必须为"开启"或"关闭"')
                continue

            self.station_mgr.set_status(sel.station_id, new_status)
            updated += 1
            print(f"修改站点: {sel.name}({sel.line}) -> 状态: {new_status}")

        print(f"{updated} 个站点的状态修改完成。")
        self.station_mgr.save()

    def _show_closed(self) -> None:
        """M2-3: 显示当前关闭站点。"""
        closed = self.station_mgr.closed_stations()
        if not closed:
            print("所有站点均处于开放状态。")
            return

        print(f"当前关闭站点（共 {len(closed)} 个）：")
        for s in closed:
            print(f"  · {s.name}（{s.line}）")

    def _restore_initial(self) -> None:
        """M2-4: 恢复所有站点初始状态。"""
        if not read_yes_no():
            print("已取消恢复。")
            return

        if self.station_mgr.restore_initial():
            self.station_mgr.save()
            print(f"已成功恢复 {len(self.station_mgr)} 个站点至初始状态。")
        else:
            print("无法打开初始化文件或无法写入目标文件。")

    def _show_line_info(self) -> None:
        """M2-5: 显示线路站点信息。"""
        print("请输入线路编号（1-18, 41, 51）: ", end="")
        try:
            ln = int(input().strip())
        except ValueError:
            print("线路编号无效。")
            return

        line_name_map = {
            1: "1号线", 2: "2号线", 3: "3号线", 4: "4号线",
            5: "5号线", 6: "6号线", 7: "7号线", 8: "8号线",
            9: "9号线", 10: "10号线", 11: "11号线", 12: "12号线",
            13: "13号线", 14: "14号线", 15: "15号线", 16: "16号线",
            17: "17号线", 18: "18号线", 41: "浦江线", 51: "市域机场线",
        }
        line_name = line_name_map.get(ln)
        if line_name is None or (ln < 1 or (ln > 18 and ln not in (41, 51))):
            print("线路编号无效。")
            return

        stations = self.station_mgr.stations_of_line(line_name)
        if not stations:
            print(f"未找到 {line_name} 的站点信息。")
            return

        print(f"\n{line_name}（共 {len(stations)} 站）：")
        for i, s in enumerate(stations, 1):
            # 换乘线路信息
            transfer_lines = self.station_mgr.transfer_lines_for(s.name, exclude_line=s.line)
            transfer_str = ""
            if transfer_lines:
                transfer_str = f"  [换乘: {', '.join(transfer_lines)}]"
            closed_str = " [关闭]" if not s.is_open else ""
            print(f"  {i:2d}. {s.name}{transfer_str}{closed_str}")

    def _affected_analysis(self) -> None:
        """M2-6: 受关闭站点影响分析（BFS 一阶邻居）。"""
        closed = self.station_mgr.closed_stations()
        if not closed:
            print("当前无关闭站点，无需分析。")
            return

        from network_analysis import affected_area
        print(f"当前有 {len(closed)} 个关闭站点。")
        for cs in closed:
            affected_ids = affected_area(self.graph, self.station_mgr, cs.station_id)
            if not affected_ids:
                continue
            names = []
            for aid in affected_ids:
                s = self.station_mgr.get(aid)
                if s:
                    names.append(f"{s.name}({s.line})")
            if names:
                print(f"  {cs.name}({cs.line}) 关闭，直接影响: {', '.join(names[:6])}")
                if len(names) > 6:
                    print(f"    ... 及其他 {len(names)-6} 个站点")

    # ==================== 子菜单 2: 最短时间路径 ====================

    def sub_menu_shortest_time(self) -> None:
        """最短时间路径二级菜单。"""
        while True:
            print()
            print("-- 所需时间最短路径规划 --")
            print("1. 单条所需时间最短路径")
            print("2. 3条所需时间最短路径")
            print("3. 返回上级菜单")

            choice = read_menu_choice("请输入选项编号: ", 1, 3)

            if choice == 1:
                self._single_shortest_time()
            elif choice == 2:
                self._k_shortest_time(3)
            elif choice == 3:
                break

    def _single_shortest_time(self) -> None:
        """M3-1: 单条最短时间路径。"""
        src_id, dst_id = read_start_end_station(self.station_mgr, "单条所需时间最短路径")
        if src_id is None or dst_id is None:
            return

        result = dijkstra_shortest_time(src_id, dst_id, self.graph, self.station_mgr)
        print_path_header("最短时间路径结果")
        print(format_path(result, self.station_mgr, self.graph))

    def _k_shortest_time(self, k: int = 3) -> None:
        """M3-2: K 条最短时间路径。"""
        src_id, dst_id = read_start_end_station(self.station_mgr,
                                                 f"{k}条所需时间最短路径")
        if src_id is None or dst_id is None:
            return

        results = yen_k_shortest_time(src_id, dst_id, self.graph, self.station_mgr, k=k)
        for i, result in enumerate(results, 1):
            print_path_header(f"第 {i} 条最短时间路径")
            print(format_path(result, self.station_mgr, self.graph))

    # ==================== 子菜单 3: 最少换乘路径 ====================

    def sub_menu_min_transfers(self) -> None:
        """最少换乘路径二级菜单。"""
        while True:
            print()
            print("-- 所需换乘次数最少路径规划 --")
            print("1. 单条换乘次数最少路径")
            print("2. 3条换乘次数最少路径")
            print("3. 返回主菜单")

            choice = read_menu_choice("请输入选项编号: ", 1, 3)

            if choice == 1:
                self._single_min_transfer()
            elif choice == 2:
                self._k_min_transfer(3)
            elif choice == 3:
                break

    def _single_min_transfer(self) -> None:
        """M4-1: 单条最少换乘路径。"""
        src_id, dst_id = read_start_end_station(self.station_mgr,
                                                 "单条换乘次数最少路径")
        if src_id is None or dst_id is None:
            return

        result = dijkstra_min_transfers(src_id, dst_id, self.graph, self.station_mgr)
        print_path_header("最少换乘路径结果")
        print(format_path(result, self.station_mgr, self.graph))

    def _k_min_transfer(self, k: int = 3) -> None:
        """M4-2: K 条最少换乘路径。"""
        src_id, dst_id = read_start_end_station(self.station_mgr,
                                                 f"{k}条换乘次数最少路径")
        if src_id is None or dst_id is None:
            return

        results = yen_k_min_transfers(src_id, dst_id, self.graph, self.station_mgr, k=k)
        for i, result in enumerate(results, 1):
            print_path_header(f"第 {i} 条最少换乘路径")
            print(format_path(result, self.station_mgr, self.graph))
