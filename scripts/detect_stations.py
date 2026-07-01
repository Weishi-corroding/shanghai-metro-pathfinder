"""
detect_stations.py - Phase 2 站点检测

策略：
1. 将掩膜骨架化得到线路骨架
2. 骨架上检测特征点（间隙）得到站点位置
3. 输出检测到的站点坐标到 debug 图像
"""

import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "metroView.jpg"
DEBUG_DIR = ROOT / "scripts" / "_metro_debug"

# 所有线路颜色 (BGR)
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
    """从 HSV 图中提取一条线路的掩膜"""
    target_hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
    h_target = int(target_hsv[0])

    if h_target < 10 or h_target > 170:
        # 红色跨越 H=0/180 边界
        lower1 = np.array([0, 80, 60])
        upper1 = np.array([10, 255, 255])
        lower2 = np.array([170, 80, 60])
        upper2 = np.array([179, 255, 255])
        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    else:
        lower = np.array([max(0, h_target - 10), 80, 60])
        upper = np.array([min(179, h_target + 10), 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

    # 形态学操作：细线膨胀消除噪点，再膨胀连接断裂
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # 先闭运算连接断裂
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)   # 开运算去噪

    return mask


def skeletonize(mask):
    """骨架化：将线路变成1像素宽度的骨架"""
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


def find_station_points(skel, min_gap=6):
    """从骨架上找站点位置。
    站点在骨架上表现为线段的端点或分叉点，
    或者沿线局部距离变换的极值点。
    """
    # 方法：沿骨架检测特征点
    points = []

    # 1. 距离变换
    dist = cv2.distanceTransform(skel, cv2.DIST_L2, 3)

    # 2. 找骨架上的所有点
    ys, xs = np.where(skel > 0)

    # 3. 沿骨架找局部极值（站点处骨架变粗）
    for y, x in zip(ys, xs):
        # 看周围像素的距离变换值是否局部最大
        if y < 2 or y >= dist.shape[0] - 2 or x < 2 or x >= dist.shape[1] - 2:
            continue
        local_max = dist[y, x]
        is_local_max = True
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                if dist[y + dy, x + dx] > local_max:
                    is_local_max = False
                    break
            if not is_local_max:
                break
        if is_local_max:
            points.append((x, y))

    # NMS 去重（相距 min_gap 内的合并）
    points = sorted(points, key=lambda p: (p[0] // min_gap, p[1] // min_gap))
    deduped = []
    last_p = None
    for p in points:
        if last_p is None:
            deduped.append(p)
            last_p = p
        else:
            dx = p[0] - last_p[0]
            dy = p[1] - last_p[1]
            if dx*dx + dy*dy > min_gap*min_gap:
                deduped.append(p)
                last_p = p

    return deduped


def main():
    print(f"Loading image from {IMG_PATH}")
    img = cv2.imread(str(IMG_PATH))
    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 测试几条线路
    test_lines = ["1号线", "2号线", "8号线"]

    for line_name in test_lines:
        bgr = LINE_COLORS_BGR[line_name]
        print(f"\nProcessing {line_name}...")

        # 1. 颜色掩膜
        mask = extract_line_mask(hsv, bgr)
        print(f"  Mask pixels: {np.sum(mask > 0)}")

        # 2. 骨架化
        skel = skeletonize(mask)
        print(f"  Skeleton pixels: {np.sum(skel > 0)}")

        # 3. 检测站点
        stations = find_station_points(skel)
        print(f"  Detected stations: {len(stations)}")

        # 4. 生成可视化
        # 将结果叠加到原图上
        vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        # 红圈标记站点
        for (x, y) in stations:
            cv2.circle(vis, (x, y), 8, (0, 0, 255), 2)

        # 保存缩略图
        scale = 0.25
        vis_small = cv2.resize(vis, None, fx=scale, fy=scale)
        out_path = DEBUG_DIR / f"2_stations_{line_name}.jpg"
        cv2.imwrite(str(out_path), vis_small)
        print(f"  Saved to {out_path.name}")

    # 尝试检测所有线路
    print(f"\nProcessing ALL lines and generating composite...")
    all_stations = set()

    # 为了去重，先收集所有线路的站点
    composite = img.copy()
    colors_list = list(LINE_COLORS_BGR.values())
    for i, (line_name, bgr) in enumerate(LINE_COLORS_BGR.items()):
        mask = extract_line_mask(hsv, bgr)
        skel = skeletonize(mask)
        stations = find_station_points(skel)
        for s in stations:
            all_stations.add(s)
        # 在 composite 上用颜色稍微高亮线路
        for (x, y) in stations:
            cv2.circle(composite, (x, y), 6, bgr, -1)
        print(f"  {line_name}: {len(stations)} stations")

    # 保存全局站点图
    scale = 0.2
    composite_small = cv2.resize(composite, None, fx=scale, fy=scale)
    cv2.imwrite(str(DEBUG_DIR / "3_all_stations.jpg"), composite_small)
    print(f"\nTotal stations detected: {len(all_stations)}")
    print(f"Composite saved to 3_all_stations.jpg")

    # 保存检测到的坐标（原始分辨率）
    coords_path = DEBUG_DIR / "detected_coords_raw.txt"
    with open(coords_path, "w", encoding="utf-8") as f:
        for x, y in sorted(all_stations):
            f.write(f"{x},{y}\n")
    print(f"Raw coordinates saved to {coords_path.name}")


if __name__ == "__main__":
    main()
