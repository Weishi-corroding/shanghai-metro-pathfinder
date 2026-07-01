"""
detect_stations_v2.py - 改进的站点检测

思路：站点在线路上是等距分布的（约 50-80px 一个），
因此用距离变换 + 形态学检测，而不是找每个局部最大值。
"""

import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "metroView.jpg"
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


def extract_line_mask(hsv, bgr):
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
    return mask


def skeletonize(mask):
    skel = np.zeros(mask.shape, np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while True:
        eroded = cv2.erode(mask, kernel)
        temp = cv2.dilate(eroded, kernel)
        temp = cv2.subtract(mask, temp)
        skel = cv2.bitwise_or(skel, temp)
        mask = eroded.copy()
        if cv2.countNonZero(mask) == 0:
            break
    return skel


def find_stations_by_sampling(skel, station_spacing=55):
    """通过骨架上的等距采样找站点。
    上海地铁图中站点间距约 50-60 像素（原图分辨率）。
    """
    # 找所有骨架点
    ys, xs = np.where(skel > 0)
    if len(ys) == 0:
        return []

    visited = np.zeros_like(skel, dtype=bool)
    stations = []

    for y, x in zip(ys, xs):
        if visited[y, x]:
            continue

        # 开始跟踪一条线段
        current_x, current_y = x, y
        path = []

        while True:
            visited[current_y, current_x] = True
            path.append((current_x, current_y))

            # 找下一个未访问的邻接点
            found = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = current_x + dx, current_y + dy
                    if (0 <= ny < skel.shape[0] and 0 <= nx < skel.shape[1]
                            and skel[ny, nx] and not visited[ny, nx]):
                        current_x, current_y = nx, ny
                        found = True
                        break
                if found:
                    break
            if not found:
                break

        # 从路径中按间距采样站点
        total_dist = 0
        for i in range(len(path) - 1):
            dx = path[i+1][0] - path[i][0]
            dy = path[i+1][1] - path[i][1]
            total_dist += (dx*dx + dy*dy)**0.5

        # 估计站点数
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
    min_dist_sq = (station_spacing * 0.6)**2
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


def main():
    print(f"Loading image from {IMG_PATH}")
    img = cv2.imread(str(IMG_PATH))
    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    test_lines = ["1号线", "2号线", "8号线"]
    for line_name in test_lines:
        bgr = LINE_COLORS_BGR[line_name]
        print(f"\nProcessing {line_name}...")

        mask = extract_line_mask(hsv, bgr)
        skel = skeletonize(mask)
        stations = find_stations_by_sampling(skel, station_spacing=55)
        print(f"  Detected stations: {len(stations)}")

        vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        for (x, y) in stations:
            cv2.circle(vis, (x, y), 10, (0, 0, 255), 3)

        scale = 0.25
        vis_small = cv2.resize(vis, None, fx=scale, fy=scale)
        out_path = DEBUG_DIR / f"4_stations_v2_{line_name}.jpg"
        cv2.imwrite(str(out_path), vis_small)
        print(f"  Saved to {out_path.name}")

    # 所有线路
    print(f"\nProcessing ALL lines (this takes time)...")
    composite = img.copy()
    all_stations = set()
    station_counts = {}

    for line_name, bgr in LINE_COLORS_BGR.items():
        mask = extract_line_mask(hsv, bgr)
        skel = skeletonize(mask)
        stations = find_stations_by_sampling(skel, station_spacing=55)
        station_counts[line_name] = len(stations)
        for s in stations:
            all_stations.add(s)
        # 在 composite 上标记
        for (x, y) in stations:
            cv2.circle(composite, (x, y), 6, bgr, -1)
        print(f"  {line_name}: {len(stations)} stations")

    # 保存结果
    scale = 0.2
    composite_small = cv2.resize(composite, None, fx=scale, fy=scale)
    cv2.imwrite(str(DEBUG_DIR / "5_all_stations_v2.jpg"), composite_small)

    print(f"\nTotal stations detected: {len(all_stations)}")
    print(f"Expected: ~530")
    print(f"Ratio: {len(all_stations) / 530:.1f}x")

    # 保存坐标到 CSV
    csv_path = DEBUG_DIR / "station_coords_v2.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("x,y\n")
        for x, y in sorted(all_stations):
            f.write(f"{x},{y}\n")
    print(f"\nCoordinates saved to {csv_path}")


if __name__ == "__main__":
    main()
