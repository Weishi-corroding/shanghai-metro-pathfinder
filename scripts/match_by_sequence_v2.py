"""
match_by_sequence_v2.py - Phase 3 改进版：沿骨架跟踪站点

问题：之前采样太密（70px），实际站点间距约 130-150px
改进：
1. 更合理的采样间距
2. 基于路径的准确跟踪
3. 输出 JSON 供前端使用
"""

import csv
import cv2
import json
import numpy as np
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "metroView.jpg"
DATA_DIR = ROOT / "python" / "data"
OUTPUT_JSON = ROOT / "cpp" / "backend" / "static" / "octilinear_from_image.json"

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
    "浦江线": (0xB6, 0xB5, 0xB5),
    "市域机场线": (0xA4, 0x90, 0x4A),
}


def load_stations():
    stations = {}
    name_to_ids = defaultdict(list)
    with open(DATA_DIR / "Station.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["站点ID"]
            name = row["站点名称"].strip()
            line = row["所属线路"].strip()
            stations[sid] = {"name": name, "line": line}
            name_to_ids[name].append(sid)
    return stations, name_to_ids


def load_line_sequences():
    """加载每条线路的站点顺序"""
    line_edges = defaultdict(list)
    with open(DATA_DIR / "Edge.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            a, b, line = row["起点站ID"], row["终点站ID"], row["线路"].strip()
            if line != "换乘":
                line_edges[line].append((a, b))

    line_sequences = {}
    for line, edges in line_edges.items():
        neighbors = defaultdict(list)
        for a, b in edges:
            neighbors[a].append(b)
            neighbors[b].append(a)

        degree = {n: len(neighbors[n]) for n in neighbors}
        start = None
        for n, d in degree.items():
            if d == 1:
                start = n
                break
        if not start:
            start = next(iter(degree.keys()))

        visited = set([start])
        seq = [start]
        current = start
        while len(seq) < len(degree):
            found = False
            for n in neighbors[current]:
                if n not in visited:
                    visited.add(n)
                    seq.append(n)
                    current = n
                    found = True
                    break
            if not found:
                break
        line_sequences[line] = seq
    return line_sequences


def get_line_mask_and_skeleton(hsv, bgr):
    """提取线路掩膜和骨架"""
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

    return skel


def sample_stations_along_skel(skel, station_spacing=140):
    """沿骨架按固定间距采样，得到站点位置"""
    ys, xs = np.where(skel > 0)
    if len(ys) == 0:
        return []

    h, w = skel.shape
    visited = np.zeros((h, w), dtype=bool)
    all_points = []

    for y, x in zip(ys, xs):
        if visited[y, x]:
            continue

        # 跟踪整条路径
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
                    if (0 <= ny < h and 0 <= nx < w and
                            skel[ny, nx] and not visited[ny, nx]):
                        cx, cy = nx, ny
                        found = True
                        break
                if found:
                    break
            if not found:
                break

        # 计算路径总长
        total_dist = 0
        seg_lens = []
        for i in range(len(path) - 1):
            dx = path[i+1][0] - path[i][0]
            dy = path[i+1][1] - path[i][1]
            l = (dx*dx + dy*dy)**0.5
            seg_lens.append(l)
            total_dist += l

        # 按间距采样
        if total_dist < station_spacing * 0.5:
            # 短路径：取中点
            all_points.append(path[len(path) // 2])
            continue

        n_samples = max(1, int(round(total_dist / station_spacing)))
        if n_samples == 1:
            all_points.append(path[len(path) // 2])
        else:
            step = total_dist / (n_samples - 1)
            acc_dist = 0
            next_sample = 0
            for i in range(len(path) - 1):
                l = seg_lens[i]
                while next_sample <= acc_dist + l + 1e-6:
                    t = (next_sample - acc_dist) / l if l > 0 else 0
                    sx = int(path[i][0] + t * (path[i+1][0] - path[i][0]) + 0.5)
                    sy = int(path[i][1] + t * (path[i+1][1] - path[i][1]) + 0.5)
                    all_points.append((sx, sy))
                    next_sample += step
                    if next_sample > total_dist + 1:
                        break
                acc_dist += l

    # NMS: 相距小于 0.6*spacing 的点合并
    all_points = sorted(all_points)
    min_dist_sq = (station_spacing * 0.6)**2
    deduped = []
    for p in all_points:
        ok = True
        for q in deduped:
            dx = p[0] - q[0]
            dy = p[1] - q[1]
            if dx*dx + dy*dy < min_dist_sq:
                ok = False
                break
        if ok:
            deduped.append(p)

    return deduped


def coord_to_svg(x, y, img_w=5497, img_h=7693, target_w=1600, target_h=1100):
    """将图像坐标缩放到与现有 layout.json 兼容的 SVG 坐标"""
    # 保持宽高比的缩放
    scale = min(target_w / img_w, target_h / img_h)
    return round(x * scale, 1), round(y * scale, 1)


def main():
    print("=" * 60)
    print("上海地铁官方图坐标提取")
    print("=" * 60)

    stations, _ = load_stations()
    line_sequences = load_line_sequences()
    print(f"Total stations: {len(stations)}")
    print(f"Lines: {len(line_sequences)}")

    print("\nLoading image...")
    img = cv2.imread(str(IMG_PATH))
    h, w = img.shape[:2]
    print(f"Image: {w}x{h}")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 结果：station_id -> {x, y, name, line, color}
    result = {}
    total_detected = 0

    for line_name in sorted(LINE_COLORS_BGR.keys()):
        if line_name not in line_sequences:
            print(f"  {line_name}: 不在数据中，跳过")
            continue

        bgr = LINE_COLORS_BGR[line_name]
        expected = len(line_sequences[line_name])

        # 用更合理的间距：1号线约38站，长度约5000px，间距约130px
        skel = get_line_mask_and_skeleton(hsv, bgr)
        points = sample_stations_along_skel(skel, station_spacing=140)

        # 将坐标映射到 SVG 坐标系
        points_svg = [coord_to_svg(x, y) for x, y in points]

        # 构建结果
        seq = line_sequences[line_name]
        color = f"#{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"

        # 这里是简化版：按顺序分配坐标给站点
        # 更准确的做法需要人工检查每个站点位置，这里先生成数据
        if len(points_svg) >= len(seq):
            # 检测到的点更多，取中间连续的一段
            offset = (len(points_svg) - len(seq)) // 2
            used_points = points_svg[offset:offset+len(seq)]
        else:
            # 检测点不足，插值补充
            used_points = points_svg[:]
            while len(used_points) < len(seq):
                # 在相邻点间插值
                inserted = False
                for i in range(len(used_points) - 1):
                    x0, y0 = used_points[i]
                    x1, y1 = used_points[i+1]
                    mx = (x0 + x1) / 2
                    my = (y0 + y1) / 2
                    dx, dy = x1 - x0, y1 - y0
                    if dx*dx + dy*dy > 2500:  # 间距>50px才插
                        used_points.insert(i+1, (mx, my))
                        inserted = True
                        break
                if not inserted:
                    break

        # 分配坐标给站点（按顺序，人工后续调整）
        for i, sid in enumerate(seq):
            if i < len(used_points):
                x, y = used_points[i]
            else:
                x, y = used_points[-1] if used_points else (0, 0)
            result[sid] = {
                "x": x, "y": y,
                "name": stations[sid]["name"],
                "line": stations[sid]["line"],
                "color": color,
            }
        total_detected += len(used_points)
        print(f"  {line_name}: {len(used_points)} stations (expected {expected})")

    # 生成线路段信息（用于绘制线路）
    lines_output = {}
    for line_name in sorted(line_sequences.keys()):
        if line_name not in LINE_COLORS_BGR:
            continue  # 跳过未知线路
        seq = line_sequences[line_name]
        color = LINE_COLORS_BGR[line_name]
        color_hex = f"#{color[2]:02X}{color[1]:02X}{color[0]:02X}"
        segments = []
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i+1]
            if a in result and b in result:
                segments.append([a, b, 0.0])  # offset=0
        lines_output[line_name] = {
            "name": line_name,
            "color": color_hex,
            "station_count": len(seq),
            "station_ids": seq,
            "segments": segments,
        }

    # 输出 JSON
    output = {
        "meta": {
            "total_stations": len(result),
            "total_lines": len(lines_output),
            "description": "Shanghai Metro schematic layout extracted from official map (metroView.jpg)",
            "octilinear": True,
        },
        "stations": result,
        "lines": lines_output,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"完成！共提取 {len(result)} 个站点坐标")
    print(f"输出文件: {OUTPUT_JSON}")
    print(f"请在浏览器中打开 index.html 查看效果，然后人工校正站点位置")


if __name__ == "__main__":
    main()
