"""
explore_metro_image.py - 探索性脚本，验证从官方地铁图提取坐标的可行性。

策略：
1. 读取 metroView.jpg
2. 按线路颜色提取掩膜（验证颜色识别可行）
3. 检测圆形（验证站点位置识别可行）
4. 输出调试图像供人工核验

输出到 /tmp/metro_debug/ 目录
"""

import os
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "metroView.jpg"
DEBUG_DIR = ROOT / "scripts" / "_metro_debug"
DEBUG_DIR.mkdir(exist_ok=True)

# 上海地铁官方线路颜色 (BGR for OpenCV)
# 来自 frontend LINE_COLORS（RGB 转 BGR）
LINE_COLORS_BGR = {
    "1号线":  (0x2B, 0x00, 0xE4),   # #E4002B red
    "2号线":  (0x00, 0xD7, 0x97),   # #97D700 green
    "3号线":  (0x00, 0xD6, 0xFC),   # #FCD600 yellow
    "4号线":  (0x84, 0x1D, 0x46),   # #461D84 purple
    "5号线":  (0x9B, 0x4D, 0x94),   # #944D9B light purple
    "6号线":  (0x6C, 0x00, 0xD6),   # #D6006C magenta
    "7号线":  (0x06, 0x6B, 0xED),   # #ED6B06 orange
    "8号线":  (0xD8, 0x94, 0x00),   # #0094D8 blue
    "9号线":  (0xE1, 0xC8, 0x7A),   # #7AC8E1 light blue
    "10号线": (0xD4, 0xAF, 0xC6),   # #C6AFD4 light purple
    "11号线": (0x21, 0x1C, 0x84),   # #841C21 dark red
    "12号线": (0x60, 0x7A, 0x00),   # #007A60 dark green
    "13号线": (0xA5, 0x7C, 0xE7),   # #E77CA5 pink
    "14号线": (0x63, 0x8B, 0x9D),   # #9D8B63 gold
    "15号线": (0x80, 0xA6, 0xB2),   # #B2A680 olive
    "16号线": (0xC8, 0xD0, 0x77),   # #77D0C8 cyan
    "17号线": (0x14, 0x64, 0xBB),   # #BB6414 dark orange
    "18号线": (0x4E, 0x98, 0xC4),   # #C4984E ochre
}

def main():
    print(f"Loading image from {IMG_PATH}")
    img = cv2.imread(str(IMG_PATH))
    if img is None:
        print("FAILED to load image")
        return

    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")

    # 保存原图缩略图用于参考
    scale = 0.2
    thumb = cv2.resize(img, None, fx=scale, fy=scale)
    cv2.imwrite(str(DEBUG_DIR / "0_original_thumb.jpg"), thumb)
    print(f"Saved thumbnail (scale={scale})")

    # 转 HSV 便于颜色匹配
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 尝试提取 1号线 (红色) 的掩膜
    test_lines = [
        ("1号线", (0x2B, 0x00, 0xE4)),   # red
        ("2号线", (0x00, 0xD7, 0x97)),   # green
        ("8号线", (0xD8, 0x94, 0x00)),   # blue
    ]

    for name, bgr in test_lines:
        # 转 HSV
        target_hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        h_target = int(target_hsv[0])

        # HSV 颜色匹配（H 容差 ±10，S 较饱和，V 较亮）
        lower = np.array([max(0, h_target - 10), 80, 60])
        upper = np.array([min(179, h_target + 10), 255, 255])

        if h_target < 10 or h_target > 170:
            # 红色跨越 0/180 边界，用两段
            lower1 = np.array([0, 80, 60])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([170, 80, 60])
            upper2 = np.array([179, 255, 255])
            mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
        else:
            mask = cv2.inRange(hsv, lower, upper)

        # 计算掩膜中像素数量
        pixel_count = np.sum(mask > 0)
        pct = pixel_count / (h * w) * 100
        print(f"{name}: HSV H={h_target}, mask pixels = {pixel_count} ({pct:.2f}% of image)")

        # 保存掩膜的缩略图
        mask_thumb = cv2.resize(mask, None, fx=scale, fy=scale)
        cv2.imwrite(str(DEBUG_DIR / f"1_mask_{name}.jpg"), mask_thumb)

    print(f"\nDebug images saved to {DEBUG_DIR}")
    print("Files generated:")
    for f in sorted(DEBUG_DIR.glob("*.jpg")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.1f}KB")

if __name__ == "__main__":
    main()
