"""
utils.py — 工具函数（输入处理、模糊匹配、显示格式化）
======================================================
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from station import StationManager


# ---------------------------------------------------------------------------
# 输入处理（M1: 非法输入校验）
# ---------------------------------------------------------------------------

def read_menu_choice(prompt: str = "请输入选项编号: ",
                     min_val: int = 1, max_val: int = 4) -> int:
    """读取菜单选项，自动处理非法输入（M1 要求）。

    非法输入类型（全部返回非异常）:
      - 非数字字符串 → 提示、重试
      - 浮点数 → 提示、重试
      - 越界数字 → 提示、重试
      - 负数 → 提示、重试
    """
    while True:
        try:
            raw = input(prompt).strip()
            val = int(raw)
            if val < min_val or val > max_val:
                print(f"输入无效，请输入数字选项{min_val}、{max_val}")
                continue
            return val
        except ValueError:
            print(f"输入无效，请输入数字选项{min_val}、{max_val}")
            continue


def read_int(prompt: str) -> int:
    """读取整数，出错时提示。"""
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("输入无效，请输入有效整数。")
            continue


def read_yes_no(prompt: str = "您确定要恢复所有站点的初始状态? (Y/N): ") -> bool:
    """Y/N 确认。"""
    while True:
        ans = input(prompt).strip().upper()
        if ans == "Y":
            return True
        if ans == "N":
            return False
        print("请输入 Y 或 N。")


# ---------------------------------------------------------------------------
# 站名模糊匹配（M3/M4: 模糊关键词检索）
# ---------------------------------------------------------------------------

def fuzzy_select_station(station_mgr: StationManager,
                         keyword: str | None = None,
                         prompt_text: str = "请输入站点关键词: ") -> str | None:
    """模糊匹配站名，让用户从候选项中选择，返回 station_id。

    M3/M4 要求：
      - 输入"上海体" → 列出: 1. 上海体育馆(1号线)  2. 上海体育馆(4号线) 等
      - 无匹配 → 提示"未找到匹配的站点，请重新选择"
      - 唯一匹配 → 直接返回
    """
    if keyword is None:
        keyword = input(prompt_text).strip()

    if not keyword:
        print("未找到匹配的站点，请重新选择。")
        return None

    # 精确匹配优先
    exact = station_mgr.find_by_name(keyword)
    candidates = exact if exact else station_mgr.find_fuzzy(keyword)

    if not candidates:
        print("未找到匹配的站点，请重新选择。")
        return None

    if len(candidates) == 1:
        return candidates[0].station_id

    # 多候选 → 列出供选择
    print(f"匹配到以下站点，请选择：")
    for i, s in enumerate(candidates, 1):
        flag = " [关闭]" if not s.is_open else ""
        print(f"  {i}. {s.name}（{s.line}）{flag}")

    while True:
        try:
            idx = int(input("请输入对应编号选择站点: ").strip())
            if 1 <= idx <= len(candidates):
                selected = candidates[idx - 1]
                if not selected.is_open:
                    print(f"所选站点 {selected.name}（{selected.line}）已关闭，请重新选择。")
                    continue
                return selected.station_id
            print(f"请输入 1~{len(candidates)} 之间的编号。")
        except ValueError:
            print("输入无效，请输入编号。")


def read_start_end_station(station_mgr: StationManager,
                            mode_name: str) -> tuple[str | None, str | None]:
    """读取起终点站名并进行模糊匹配。

    返回 (src_id, dst_id)，任一为 None 表示取消失败。
    """
    print(f"\n--- {mode_name} ---")
    src = fuzzy_select_station(station_mgr, None, "请输入起点站关键词: ")
    if src is None:
        return None, None

    dst = fuzzy_select_station(station_mgr, None, "请输入终点站关键词: ")
    if dst is None:
        return None, None

    return src, dst


# ---------------------------------------------------------------------------
# 路径格式化
# ---------------------------------------------------------------------------

def print_path_header(title: str) -> None:
    """打印带分隔线的标题。"""
    width = 56
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
