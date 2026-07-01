"""Generate 8 SVG slides for 答辩PPT-v2.0.0.

Run from project root:
    cd artifacts/ppt-v2.0.0-build
    python generate_slides.py

Outputs to svg_output/NN_name.svg, 1280x720 each.
"""
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1280, 720
OUT = Path(__file__).parent / "svg_output"
OUT.mkdir(parents=True, exist_ok=True)

# ────────── Color palette ──────────
BG = "#0B1F3A"
CARD = "#132846"
CARD_STROKE = "#1E3A5F"
TEXT_1 = "#FFFFFF"
TEXT_2 = "#DDEBFF"
TEXT_3 = "#B7C7DE"
TEXT_4 = "#91A9C8"
GOLD = "#FFD54F"
RED = "#D32F2F"
METRO_RED = "#E4002B"

# Shanghai metro real line colors (from cpp/backend/server.cpp LINE_COLORS)
LC = {
    "1": "#E4002B", "2": "#97D700", "3": "#FCD600", "4": "#461D84",
    "5": "#0094D8", "6": "#D40068", "7": "#ED8B00", "8": "#001E62",
    "9": "#87CEEB", "10": "#B65EAF", "11": "#841C21", "12": "#007A53",
    "13": "#EF95CF", "14": "#7C7B7B", "15": "#B4A76A", "16": "#5D9E68",
    "17": "#B4917F", "18": "#B48A5C",
}

FONT = "Microsoft YaHei, SimHei, Arial, sans-serif"
MONO = "Consolas, 'Courier New', monospace"


# ────────── SVG primitives ──────────
def rect(x, y, w, h, fill=CARD, stroke="none", sw=0, rx=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}/>'


def line(x1, y1, x2, y2, stroke=RED, sw=3, dash=None, cap="round"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>'


def circle(cx, cy, r, fill=TEXT_1, stroke="none", sw=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{s}/>'


def text(x, y, s, size=24, fill=TEXT_2, weight="400", anchor="start", font=FONT):
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>'
    )


def polygon(pts, fill=CARD, stroke="none", sw=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
    p = " ".join(f"{x},{y}" for x, y in pts)
    return f'<polygon points="{p}" fill="{fill}"{s}/>'


def path(d, fill="none", stroke=RED, sw=2):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def image(href, x, y, w, h, preserve="xMidYMid meet"):
    return f'<image href="{href}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="{preserve}"/>'


def write_slide(idx, name, body):
    fname = OUT / f"{idx:02d}_{name}.svg"
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
        f'  <rect width="{W}" height="{H}" fill="{BG}"/>\n'
        f'  {body}\n'
        f'</svg>\n'
    )
    fname.write_text(svg, encoding="utf-8")
    print(f"[OK] wrote {fname.name}")


# ────────── Slide 1: Cover ──────────
def slide_01_cover():
    parts = []
    # Left accent bar
    parts.append(rect(0, 0, 12, H, fill=METRO_RED))
    # Big title
    parts.append(text(80, 240, "上海地铁路径规划与运营管理系统", size=56, fill=TEXT_1, weight="700"))
    # Subtitle
    parts.append(text(80, 300, "C++17 核心 · REST 后端 · Web 可视化前端", size=28, fill=TEXT_2, weight="400"))
    # Course / school
    parts.append(text(80, 360, "东华大学 · 数据结构课程设计 · 2026-07", size=22, fill=TEXT_3))
    # Key metrics — 4 stat cards横排
    stats = [("20", "条线路"), ("530+", "个物理站"), ("1300+", "有向边"), ("18", "REST 端点")]
    for i, (num, label) in enumerate(stats):
        cx = 200 + i * 240
        parts.append(rect(cx - 100, 460, 200, 130, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
        parts.append(text(cx, 530, num, size=44, fill=GOLD, weight="700", anchor="middle"))
        parts.append(text(cx, 570, label, size=20, fill=TEXT_2, anchor="middle"))
    # Footer
    parts.append(text(80, 680, "v2.0.0 · 小组答辩版 · github.com/Weishi-corroding/shanghai-metro-pathfinder",
                       size=16, fill=TEXT_4))
    write_slide(1, "cover", "\n  ".join(parts))


# ────────── Placeholder stubs for later tasks ──────────
def slide_02_overview():
    parts = []
    # Header
    parts.append(text(80, 90, "项目概览", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 145, "三大功能模块 · 系统数据规模", size=22, fill=TEXT_3))

    # Three feature cards
    cards = [
        (80, "🗺️ 路径规划", ["最短时间 / 最少换乘", "K 优路径（K=3）", "换乘节点拆分", "Dijkstra + Yen"]),
        (470, "⚙️ 运营管理", ["单站关闭/开启", "批量 CSV 更新", "恢复初始状态", "闭站路径过滤"]),
        (860, "📊 网络分析", ["BFS 影响范围", "DFS 连通分量", "K 阶邻居", "分量数变化检测"]),
    ]
    for x, title, lines in cards:
        parts.append(rect(x, 180, 380, 260, fill=CARD, stroke=CARD_STROKE, sw=2, rx=12))
        parts.append(text(x + 20, 220, title, size=28, fill=GOLD, weight="700"))
        for i, ln in enumerate(lines):
            parts.append(text(x + 20, 280 + i * 40, ln, size=20, fill=TEXT_2))

    # Bottom metric strip
    metrics = [("20", "线路"), ("530+", "物理站"), ("800+", "图节点"),
               ("1300+", "有向边"), ("278", "换乘边"), ("41", "测试通过")]
    for i, (num, label) in enumerate(metrics):
        x = 60 + i * 195
        parts.append(rect(x, 490, 180, 130, fill=CARD, stroke=CARD_STROKE, sw=2, rx=8))
        parts.append(text(x + 90, 545, num, size=32, fill=GOLD, weight="700", anchor="middle"))
        parts.append(text(x + 90, 585, label, size=16, fill=TEXT_2, anchor="middle"))

    # Footer
    parts.append(text(80, 690, "~3,100 行 C++17 · 无第三方图库", size=16, fill=TEXT_4))
    write_slide(2, "overview", "\n  ".join(parts))


def slide_03_dataset_graph():
    parts = []
    # Header
    parts.append(text(80, 90, "数据集建设 & 图建模", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 140, "对应课设：数据集 10 + 图拓扑 10 = 20 分", size=18, fill=GOLD))

    # Pipeline flow (3 boxes)
    stages = [
        (60, "① Fetch", "python fetch_all.py", "Shanghai Metro API", "→ metro_data/line-XX.csv"),
        (460, "② Build", "build_dataset (C++)", "换乘拆分 · 边填补 · 环线去伪", "→ Station.csv, Edge.csv"),
        (860, "③ Visualize", "fetch_station_coords.py", "OSM Overpass 投影", "→ layout.json"),
    ]
    for x, tt, l1, l2, l3 in stages:
        parts.append(rect(x, 175, 340, 130, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
        parts.append(text(x + 20, 210, tt, size=22, fill=GOLD, weight="700"))
        parts.append(text(x + 20, 245, l1, size=16, fill=TEXT_2, font=MONO))
        parts.append(text(x + 20, 270, l2, size=16, fill=TEXT_3))
        parts.append(text(x + 20, 295, l3, size=14, fill=TEXT_3))

    # Arrows between stages
    for x_start in [400, 800]:
        parts.append(line(x_start, 240, x_start + 60, 240, stroke=METRO_RED, sw=3))
        parts.append(polygon([(x_start + 55, 233), (x_start + 65, 240), (x_start + 55, 247)], fill=METRO_RED))

    # Middle-left: transfer node example (60, 360, 500x230)
    parts.append(rect(60, 360, 500, 230, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 395, "换乘节点拆分（例：人民广场）", size=22, fill=GOLD, weight="700"))
    # Three colored nodes
    nodes = [(160, "1", "0113"), (310, "2", "0213"), (460, "8", "0816")]
    ny = 475
    for cx, ln_key, label in nodes:
        parts.append(circle(cx, ny, 28, fill=LC[ln_key]))
        parts.append(text(cx, ny + 8, label, size=16, fill=TEXT_1, weight="700", anchor="middle", font=MONO))
        parts.append(text(cx, ny + 55, f"{ln_key}号线", size=14, fill=TEXT_3, anchor="middle"))
    # Transfer edges (dashed) pairwise
    parts.append(line(188, ny, 282, ny, stroke=TEXT_3, sw=2, dash="6,4"))
    parts.append(line(338, ny, 432, ny, stroke=TEXT_3, sw=2, dash="6,4"))
    # curve for outer pair - just a dashed line above
    parts.append(path("M 160 447 Q 310 405 460 447", fill="none", stroke=TEXT_3, sw=2))
    parts.append(text(310, 428, "换乘 t=5", size=14, fill=TEXT_3, anchor="middle"))
    parts.append(text(80, 570, "同名站按线路拆成 3 节点 · 换乘边双向 · 边权=5min · line=换乘",
                     size=14, fill=TEXT_3))

    # Middle-right: 处理清单 (600, 360, 620x230)
    parts.append(rect(600, 360, 620, 230, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(620, 395, "特殊处理", size=22, fill=GOLD, weight="700"))
    items = [
        "▸ 4 号线环状：内圈/外圈方向标记（Line4Dir）",
        "▸ 5/10/11 支线：3min 默认补边填补 Y 分叉",
        "▸ remove_loop_closure_edges() 移除环线伪边",
        "▸ UTF-8 BOM：utf-8-sig，中文 Excel 兼容",
        "▸ StationManager 拆分同名站为独立 ID",
    ]
    for i, s in enumerate(items):
        parts.append(text(620, 430 + i * 32, s, size=18, fill=TEXT_2))

    # Bottom metrics
    parts.append(text(640, 660, "530 物理站 → 800+ 图节点   ·   1044 边段 → 1300+ 有向边   ·   278 换乘边",
                     size=20, fill=GOLD, weight="700", anchor="middle"))
    write_slide(3, "dataset_graph", "\n  ".join(parts))


def slide_04_algorithms():
    parts = []
    # Header
    parts.append(text(80, 90, "路径算法", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 140, "对应课设：路径算法 15 分", size=18, fill=GOLD))

    # Four algorithm comparison cards
    cols = [
        (60, "Dijkstra Shortest", "权重: TimeWeight", "min-heap: std::greater<>", "用途: 单源最短时间"),
        (360, "Yen K-Shortest", "算法: spur-path", "K = 3", "用途: Top-K 最短路径"),
        (660, "Dijkstra Min Xfer", "权重: (transfers, time)", "字典序比较", "用途: 最少换乘"),
        (960, "Yen K-Min Xfer", "Yen + TransferWeight", "K = 3", "用途: Top-K 最少换乘"),
    ]
    for x, tt, l1, l2, l3 in cols:
        parts.append(rect(x, 175, 280, 185, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
        parts.append(text(x + 15, 210, tt, size=22, fill=GOLD, weight="700"))
        parts.append(text(x + 15, 250, l1, size=16, fill=TEXT_2, font=MONO))
        parts.append(text(x + 15, 280, l2, size=14, fill=TEXT_2, font=MONO))
        parts.append(text(x + 15, 320, l3, size=16, fill=TEXT_3))

    # Middle-left: Dijkstra pseudo-code
    parts.append(rect(60, 390, 620, 250, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 420, "Dijkstra 主循环（简化）", size=22, fill=GOLD, weight="700"))
    code_lines = [
        "pq: priority_queue<Weight> (min-heap)",
        "pq.push({start, 0})",
        "dist[start] = 0",
        "while (!pq.empty()) {",
        "  auto [u, du] = pq.top(); pq.pop();",
        "  if (visited[u]) continue;",
        "  visited[u] = true;",
        "  for (edge : g.neighbors(u, mgr)) {",
        "    Weight nw = du + edge_weight(edge);",
    ]
    ys = [440, 462, 484, 506, 528, 550, 572, 594, 616]
    for y, s in zip(ys, code_lines):
        parts.append(text(80, y, s, size=15, fill=TEXT_2, font=MONO))

    # Middle-right: transfer count 3 rules + example (x=700, y=390, 560x250)
    parts.append(rect(700, 390, 560, 250, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(720, 420, "换乘计数三规则（v1.0.0 核心修复）", size=22, fill=GOLD, weight="700"))
    rules = [
        "① 起点上第一条线不算换乘（line_trace 不预置起点线路）",
        "② 沿途换乘计一次（新线路 ID 不等于当前线路 ID）",
        "③ 终点前最后一段换乘边不算换乘（i+1==size 特殊处理）",
    ]
    for y, s in zip([458, 486, 514], rules):
        parts.append(text(720, y, s, size=16, fill=TEXT_2))
    parts.append(line(720, 540, 1240, 540, stroke=CARD_STROKE, sw=1))
    parts.append(text(720, 568, "示例", size=22, fill=GOLD, weight="700"))
    parts.append(text(720, 596, "莘庄→陆家嘴  1 换乘（1 号线 → 2 号线）", size=15, fill=TEXT_3))
    parts.append(text(720, 620, "人民广场→陆家嘴  0 换乘（直接乘 2 号线）", size=15, fill=TEXT_3))

    write_slide(4, "algorithms", "\n  ".join(parts))

def slide_05_operations():
    pass  # Task 3

def slide_06_network_analysis():
    pass  # Task 3

def slide_07_visualization():
    pass  # Task 4

def slide_08_tests_summary():
    pass  # Task 4


if __name__ == "__main__":
    slide_01_cover()
    slide_02_overview()
    slide_03_dataset_graph()
    slide_04_algorithms()
    slide_05_operations()
    slide_06_network_analysis()
    slide_07_visualization()
    slide_08_tests_summary()
    print("[DONE] All slides generated.")
