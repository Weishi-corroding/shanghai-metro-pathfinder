"""
match_by_sequence.py - Phase 3: 利用拓扑序列匹配

已知：
1. 每条线路的站点顺序 (Station.csv/Edge.csv)
2. 从图中检测到的点云

策略：
对每条线路：
1. 提取该线路颜色的所有点
2. 从线路一端开始，按顺序用动态规划跟踪站点位置
3. 得到 站点ID → (x,y) 像素坐标
"""

import csv
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "metroView.jpg"
DATA_DIR = ROOT / "python" / "data"
DEBUG_DIR = ROOT / "scripts" / "_metro_debug"

LINE_COLORS_BGR = {
    "1号线":  (0x2B, 0x00, 0xE4),
    "2号线":  (0x00, 0xD7, 0x97),
    "3号线":  (0x00, 0xD6, 0xFC),
    "4号线":  (0x84, 0x1D, 0x46),
    "5号线":  (0x9B, 0x4D, 0x94),
    "6号线":  (0x6C, 0x00, 0xD6),
    "7号线":  (0x06, 0x6B, 0xED),
    "8号线":  (0xD8, 0x94, 0x00),
    "9号线":  (0xE1, 0xC8, 0x7A),
    "10号线": (0xD4, 0xAF, 0xC6),
    "11号线": (0x21, 0x1C, 0x84),
    "12号线": (0x60, 0x7A, 0x00),
    "13号线": (0xA5, 0x7C, 0xE7),
    "14号线": (0x63, 0x8B, 0x9D),
    "15号线": (0x80, 0xA6, 0xB2),
    "16号线": (0xC8, 0xD0, 0x77),
    "17号线": (0x14, 0x64, 0xBB),
    "18号线": (0x4E, 0x98, 0xC4),
}


def load_stations():
    """加载所有站点信息"""
    stations = {}  # id -> {name, line, ...}
    name_to_ids = defaultdict(list)  # name -> [id, id, ...] 换乘站有多个 id
    with open(DATA_DIR / "Station.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["站点ID"]
            name = row["站点名称"].strip()
            line = row["所属线路"].strip()
            stations[sid] = {"name": name, "line": line, "is_open": row["运营状态"] == "开通"}
            name_to_ids[name].append(sid)
    return stations, name_to_ids


def load_edges():
    """加载每条线路的站点顺序"""
    line_stations = defaultdict(list)  # line -> [id1, id2, ...]
    seen_pairs = set()

    with open(DATA_DIR / "Edge.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            a = row["起点站ID"]
            b = row["终点站ID"]
            line = row["线路"].strip()
            if line == "换乘":
                continue
            pair = tuple(sorted([a, b]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            line_stations[line].append((a, b))

    # 将边转化为有序列表
    line_sequences = {}
    for line, edges in line_stations.items():
        # 找起点（度为1的节点）
        degree = defaultdict(int)
        neighbors = defaultdict(list)
        for a, b in edges:
            degree[a] += 1
            degree[b] += 1
            neighbors[a].append(b)
            neighbors[b].append(a)

        # 从任意端点开始遍历
        start = None
        for n, d in degree.items():
            if d == 1:
                start = n
                break
        if not start:
            # 环线（如4号线），随便选一点
            start = next(iter(degree.keys()))

        # DFS 构建序列
        visited = set([start])
        seq = [start]
        current = start
        while len(seq) < len(degree):
            for n in neighbors[current]:
                if n not in visited:
                    visited.add(n)
                    seq.append(n)
                    current = n
                    break
            else:
                break

        line_sequences[line] = seq
        print(f"  {line}: {len(seq)} stations")

    return line_sequences


def extract_line_points(hsv, bgr, station_spacing=70):
    """提取一条线路的候选站点坐标"""
    target_hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
    h_target = int(target_hsv[0])

    if h_target < 10 or h_target > 170:
        lower1 = np.array([0, 80, 60])
        upper1 = np.array([10, 255, 255])
        lower2 = np.array([170, 80, 60])
        upper2 = np.array([179, 255, 255])
        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    else:
        lower = np.array([max(0, h_target - 10), 80, 60])
        upper = np.array([min(179, h_target + 10), 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # 骨架化
    skel = np.zeros(mask.shape, np.uint8)
    while True:
        eroded = cv2.erode(mask, kernel)
        temp = cv2.dilate(eroded, kernel)
        temp = cv2.subtract(mask, temp)
        skel = cv2.bitwise_or(skel, temp)
        mask = eroded.copy()
        if cv2.countNonZero(mask) == 0:
            break

    # 沿骨架采样站点
    ys, xs = np.where(skel > 0)
    if len(ys) == 0:
        return []

    visited = np.zeros_like(skel, dtype=bool)
    stations = []

    for y, x in zip(ys, xs):
        if visited[y, x]:
            continue
        path = []
        cx, cy = x, y
        while True:
            visited[cy, cx] = True
            path.append((cx, cy))
            found = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if (0 <= ny < skel.shape[0] and 0 <= nx < skel.shape[1]
                            and skel[ny, nx] and not visited[ny, nx]):
                        cx, cy = nx, ny
                        found = True
                        break
                if found:
                    break
            if not found:
                break

        total_dist = 0
        for i in range(len(path) - 1):
            dx = path[i+1][0] - path[i][0]
            dy = path[i+1][1] - path[i][1]
            total_dist += (dx*dx + dy*dy)**0.5

        n_stations = max(1, int(round(total_dist / station_spacing)))
        if n_stations == 1:
            stations.append(path[len(path) // 2])
        else:
            step = total_dist / (n_stations - 1)
            acc_dist = 0
            next_station_dist = 0
            for i in range(len(path) - 1):
                dx = path[i+1][0] - path[i][0]
                dy = path[i+1][1] - path[i][1]
                seg_len = (dx*dx + dy*dy)**0.5
                while next_station_dist <= acc_dist + seg_len + 1e-6:
                    t = (next_station_dist - acc_dist) / seg_len if seg_len > 0 else 0
                    sx = int(path[i][0] + t * dx + 0.5)
                    sy = int(path[i][1] + t * dy + 0.5)
                    stations.append((sx, sy))
                    next_station_dist += step
                    if next_station_dist > total_dist + 1:
                        break
                acc_dist += seg_len

    # NMS 去重
    stations = sorted(stations)
    deduped = []
    min_dist_sq = (station_spacing * 0.5)**2
    for s in stations:
        ok = True
        for t in deduped:
            dx = s[0] - t[0]
            dy = s[1] - t[1]
            if dx*dx + dy*dy < min_dist_sq:
                ok = False
                break
        if ok:
            deduped.append(s)

    return deduped


def match_sequence_to_points(station_ids, points):
    """
    将已知的站点序列匹配到检测到的点云。
    使用贪心算法：从一端开始，每次选距离最近的未匹配点。
    """
    if len(points) == 0:
        return {}

    matched = {}
    used = set()

    # 先整体对齐：找到最左/最右的点作为端点
    points = np.array(points, dtype=np.float32)

    # 计算线路 bounding box
    min_x, min_y = points.min(axis=0)
    max_x, max_y = points.max(axis=0)
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2

    # 对于每个站点，找最近的可用点
    # 改进：用整个序列的参数化位置来匹配，而不是逐个贪心
    if len(points) < len(station_ids):
        # 检测点比实际站点少，插值补充
        pass

    # 简单贪心：按站点顺序匹配最近点
    result = {}
    points_list = [tuple(p) for p in points]

    for i, sid in enumerate(station_ids):
        if len(used) == len(points_list):
            break
        # 找最近未使用点
        best_dist = float('inf')
        best_p = None
        best_idx = -1
        for j, p in enumerate(points_list):
            if j in used:
                continue
            dist_sq = (p[0] - cx)**2 + (p[1] - cy)**2  # 临时：用中心点附近
            if dist_sq < best_dist:
                best_dist = dist_sq
                best_p = p
                best_idx = j
        if best_p is not None:
            used.add(best_idx)
            result[sid] = best_p

    # 这个简单实现只是占位，实际需要：
    # 1. 沿线路骨架跟踪
    # 2. 用 DTW（动态时间规整）匹配序列

    return result


def main():
    print("Loading data files...")
    stations, name_to_ids = load_stations()
    print(f"  Total stations: {len(stations)}")

    line_sequences = load_edges()
    print(f"  Lines: {len(line_sequences)}")

    print("\nLoading image...")
    img = cv2.imread(str(IMG_PATH))
    h, w = img.shape[:2]
    print(f"  Image: {w}x{h}")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 测试 1号线：提取点 + 匹配序列
    test_lines = ["1号线"]
    final_coords = {}  # station_id -> (x, y)

    for line_name in test_lines:
        print(f"\nProcessing {line_name}...")
        bgr = LINE_COLORS_BGR[line_name]
        points = extract_line_points(hsv, bgr, station_spacing=70)
        print(f"  Detected points: {len(points)}")
        print(f"  Expected stations: {len(line_sequences.get(line_name, []))}")

        # 在图上标记检测到的点
        for (x, y) in points:
            cv2.circle(img, (x, y), 8, bgr, -1)
            cv2.circle(img, (x, y), 12, bgr, 2)

        # 匹配序列（简化版）
        if line_name in line_sequences:
            seq = line_sequences[line_name]
            # 这里：真实的匹配需要沿线骨架追踪，暂时先标记点输出
            print(f"  Sequence: {[stations[s]['name'] for s in seq[:5]]}...")

        final_coords[line_name] = points

    # 保存可视化
    scale = 0.25
    vis_small = cv2.resize(img, None, fx=scale, fy=scale)
    cv2.imwrite(str(DEBUG_DIR / "6_matched_1号线.jpg"), vis_small)
    print(f"\nVisualization saved")

    # 保存匹配结果
    with open(DEBUG_DIR / "matched_coords.csv", "w", encoding="utf-8") as f:
        f.write("station_id,line_name,x,y\n")
        for line_name, points in final_coords.items():
            for (x, y) in points:
                f.write(f",{line_name},{x},{y}\n")

    print("\nDone! Next step: proper sequence matching along skeleton")


if __name__ == "__main__":
    main()
