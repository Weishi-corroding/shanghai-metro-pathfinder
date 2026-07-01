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

# Shanghai metro real line colors, synced to cpp/backend/server.cpp LINE_COLORS
LC = {
    "1": "#E4002B", "2": "#97D700", "3": "#FCD600", "4": "#461D84",
    "5": "#944D9B", "6": "#D6006C", "7": "#ED6B06", "8": "#0094D8",
    "9": "#7AC8E1", "10": "#C6AFD4", "11": "#841C21", "12": "#007A60",
    "13": "#E77CA5", "14": "#9D8B63", "15": "#B2A680", "16": "#77D0C8",
    "17": "#BB6414", "18": "#C4984E",
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
    parts = []
    # Header
    parts.append(text(80, 90, "运营管理（M2）", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 140, "对应课设：运营管理 15 分", size=18, fill=GOLD))

    # Upper: three scenario cards (y=175~380, 380x205 each)
    scenarios = [
        (60, "🔒 单站关闭/开启", [
            ("POST /api/stations/<id>/close", MONO, 15, TEXT_2),
            ("POST /api/stations/<id>/open",  MONO, 15, TEXT_2),
            ("→ StationManager.set_status()", FONT, 16, TEXT_3),
            ("锁: unique_lock (写)",            FONT, 16, TEXT_3),
        ]),
        (460, "📦 批量 CSV 更新", [
            ("POST /api/stations/batch-update", MONO, 15, TEXT_2),
            ("multipart/form-data 上传",         FONT, 16, TEXT_3),
            ("处理 update_station_status.csv",   FONT, 16, TEXT_3),
            ("返回逐行诊断报告",                    FONT, 16, TEXT_3),
        ]),
        (860, "↩️ 恢复初始", [
            ("POST /api/stations/restore",  MONO, 15, TEXT_2),
            ("→ Station_init.csv 快照",       FONT, 16, TEXT_3),
            ("build_dataset 生成时留存",       FONT, 16, TEXT_3),
            ("一键完全复原",                   FONT, 16, TEXT_3),
        ]),
    ]
    for x, title, lines in scenarios:
        parts.append(rect(x, 175, 380, 205, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
        parts.append(text(x + 20, 215, title, size=24, fill=GOLD, weight="700"))
        for i, (s, fnt, sz, clr) in enumerate(lines):
            parts.append(text(x + 20, 260 + i * 32, s, size=sz, fill=clr, font=fnt))

    # Middle: 闭站过滤原理图 (y=400~600, 780x200 at x=60)
    parts.append(rect(60, 400, 780, 200, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 430, "闭站路径过滤（Graph::neighbors 内部逻辑）", size=22, fill=GOLD, weight="700"))
    # Three station nodes: A (open), B (closed, red border), C (open)
    ax, ay = 180, 510
    bx, by = 400, 510
    cx, cy = 620, 510
    # Draw edges first, so nodes overlay endpoints
    # A→B: dim edge + red X
    parts.append(line(ax, ay, bx, by, stroke="#4A6280", sw=2))
    # X at midpoint of A-B
    mAB_x, mAB_y = (ax + bx) // 2, (ay + by) // 2
    parts.append(line(mAB_x - 10, mAB_y - 10, mAB_x + 10, mAB_y + 10, stroke=METRO_RED, sw=3))
    parts.append(line(mAB_x - 10, mAB_y + 10, mAB_x + 10, mAB_y - 10, stroke=METRO_RED, sw=3))
    # A→C: normal edge (drawn as curve above so it doesn't overlap A-B directly)
    parts.append(path(f"M {ax} {ay} Q {(ax+cx)//2} {ay - 60} {cx} {cy}", fill="none", stroke=LC["2"], sw=3))
    # C→B: dim edge + red X
    parts.append(line(cx, cy, bx, by, stroke="#4A6280", sw=2))
    mCB_x, mCB_y = (cx + bx) // 2, (cy + by) // 2
    parts.append(line(mCB_x - 10, mCB_y - 10, mCB_x + 10, mCB_y + 10, stroke=METRO_RED, sw=3))
    parts.append(line(mCB_x - 10, mCB_y + 10, mCB_x + 10, mCB_y - 10, stroke=METRO_RED, sw=3))
    # Nodes
    parts.append(circle(ax, ay, 32, fill=LC["2"]))
    parts.append(text(ax, ay + 7, "A", size=22, fill=TEXT_1, weight="700", anchor="middle"))
    parts.append(text(ax, ay + 60, "起点（开）", size=14, fill=TEXT_3, anchor="middle"))
    # B closed (red border, dark fill)
    parts.append(circle(bx, by, 32, fill="#3A0F14", stroke=METRO_RED, sw=3))
    parts.append(text(bx, by + 7, "B", size=22, fill=METRO_RED, weight="700", anchor="middle"))
    parts.append(text(bx, by + 60, "闭站", size=14, fill=METRO_RED, anchor="middle"))
    parts.append(circle(cx, cy, 32, fill=LC["2"]))
    parts.append(text(cx, cy + 7, "C", size=22, fill=TEXT_1, weight="700", anchor="middle"))
    parts.append(text(cx, cy + 60, "邻站（开）", size=14, fill=TEXT_3, anchor="middle"))
    # Annotation
    parts.append(text(720, 500, "闭站节点 B", size=16, fill=METRO_RED, weight="700"))
    parts.append(text(720, 522, "被过滤", size=16, fill=METRO_RED, weight="700"))

    # Middle-right: 前端 UI 缩略 (y=400~600, 340x200 at x=880)
    parts.append(rect(880, 400, 340, 200, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(900, 430, "Web 管理 UI", size=20, fill=GOLD, weight="700"))
    # Placeholder rect 300x140 at (900, 445), dashed border
    parts.append(rect(900, 445, 300, 140, fill="#0F2A45", stroke=CARD_STROKE, sw=1))
    # Dashed overlay border using stroke-dasharray on a transparent rect
    parts.append(
        f'<rect x="900" y="445" width="300" height="140" fill="none" '
        f'stroke="{CARD_STROKE}" stroke-width="1.5" stroke-dasharray="6,4"/>'
    )
    parts.append(text(1050, 520, "线路筛选 + 状态切换 + CSV 上传",
                     size=14, fill=TEXT_3, anchor="middle"))

    # Bottom: 实测数据 (y=630~700), three items horizontally
    parts.append(text(60,   670, "批量更新 41 站 <10ms",       size=18, fill=TEXT_2))
    parts.append(text(500,  670, "受影响路径实时重算",         size=18, fill=TEXT_2))
    parts.append(text(900,  670, "线程安全（shared_mutex）",   size=18, fill=TEXT_2))
    # 下方说明关于换乘边永不封锁
    parts.append(text(80, 618, "但换乘边永不封锁 —— 换乘节点属同一物理站的不同平台",
                     size=16, fill=TEXT_3))

    write_slide(5, "operations", "\n  ".join(parts))


def slide_06_network_analysis():
    parts = []
    # Header
    parts.append(text(80, 90, "网络分析", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 140, "对应课设：网络分析 5 分", size=18, fill=GOLD))

    # Left column: BFS 影响范围 (x=60, 550x465, y=175~640)
    parts.append(rect(60, 175, 550, 465, fill=CARD, stroke=CARD_STROKE, sw=2, rx=12))
    parts.append(text(80, 215, "🌐 BFS 影响范围", size=28, fill=GOLD, weight="700"))
    parts.append(text(80, 250, "POST /api/analysis/affected-area",
                     size=16, fill=GOLD, font=MONO))
    bfs_code = [
        "std::queue<pair<string,int>> q;",
        "q.push({start, 0});",
        "visited.insert(start);",
        "while (!q.empty()) {",
        "  auto [u, d] = q.front(); q.pop();",
        "  if (d == k) continue;",
        "  for (e : g.neighbors(u, mgr))",
        "    if (visited.insert(e.to).second)",
        "      q.push({e.to, d+1});",
        "}",
    ]
    y = 296
    for s in bfs_code:
        parts.append(text(80, y, s, size=14, fill=TEXT_2, font=MONO))
        y += 18
    parts.append(text(80, 470, "示例：关闭人民广场后 K=2", size=20, fill=TEXT_1))
    parts.append(text(80, 500, "→ 影响范围包含相邻 12 站", size=16, fill=TEXT_3))
    parts.append(text(80, 540, "复杂度 O(V+E)  ·  访问 K 阶邻居",
                     size=18, fill=GOLD, weight="700"))

    # Right column: DFS 连通分量 (x=670, 550x465)
    parts.append(rect(670, 175, 550, 465, fill=CARD, stroke=CARD_STROKE, sw=2, rx=12))
    parts.append(text(690, 215, "🔗 DFS 连通分量", size=28, fill=GOLD, weight="700"))
    parts.append(text(690, 250, "GET /api/analysis/components",
                     size=16, fill=GOLD, font=MONO))
    dfs_code = [
        "int count_components(g, mgr) {",
        "  int cnt = 0;",
        "  for (id : g.all_ids())",
        "    if (open(id) && !visited[id]) {",
        "      dfs(id, visited, g, mgr);",
        "      cnt++;",
        "    }",
        "  return cnt;",
        "}",
    ]
    y = 296
    for s in dfs_code:
        parts.append(text(690, y, s, size=14, fill=TEXT_2, font=MONO))
        y += 18
    parts.append(text(690, 470, "示例：正常运营 → 分量 = 1", size=20, fill=TEXT_1))
    parts.append(text(690, 500, "→ 关闭 4 号线所有站 → 分量 = 2+", size=16, fill=TEXT_3))
    parts.append(text(690, 540, "复杂度 O(V+E)  ·  检测图分裂",
                     size=18, fill=GOLD, weight="700"))

    # Bottom hint (centered)
    parts.append(text(W // 2, 680, "两算法均在 metro_core 中实现，前端可视化调用",
                     size=16, fill=TEXT_4, anchor="middle"))

    write_slide(6, "network_analysis", "\n  ".join(parts))

def slide_07_visualization():
    parts = []
    # Header
    parts.append(text(80, 90, "可视化与工程", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))
    parts.append(text(80, 140, "对应课设：可视化 · 端到端集成", size=18, fill=GOLD))

    # 上半：分层架构图 (y=175~370, 1160x195 at x=60)
    parts.append(rect(60, 175, 1160, 195, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 205, "系统分层", size=22, fill=GOLD, weight="700"))
    layers = [
        ("#2A4A7A", 235, "Browser (index.html + app.js + tailwind.js)"),
        ("#1E3A5F", 275, "metro_server (cpp-httplib + nlohmann/json, 18 端点)"),
        ("#152D4A", 315, "metro_core static lib (Graph, StationManager, pathfinder, analysis)"),
        ("#0F2440", 355, "python/data/ (Station.csv · Edge.csv · Station_init.csv)"),
    ]
    for fillc, ly, label in layers:
        parts.append(rect(170, ly, 900, 32, fill=fillc, stroke=CARD_STROKE, sw=1, rx=4))
        parts.append(text(185, ly + 22, label, size=16, fill=TEXT_1))
    # Arrows between layers
    parts.append(text(620, 272, "↓ HTTP/JSON", size=14, fill=TEXT_3, anchor="middle"))
    parts.append(text(620, 312, "↓ 共享", size=14, fill=TEXT_3, anchor="middle"))
    parts.append(text(620, 352, "↓", size=14, fill=TEXT_3, anchor="middle"))

    # 中下-左：UI 截图 (y=395~640, 500x245 at x=60)
    parts.append(rect(60, 395, 500, 245, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 425, "前端极简 UI（Tailwind CDN, 全离线）", size=20, fill=GOLD, weight="700"))
    parts.append(image("../images/metroView.jpg", 75, 445, 470, 180, preserve="xMidYMid meet"))
    parts.append(text(80, 635, "顶部标签 · 卡片式结果 · 路径规划/运营/分析", size=14, fill=TEXT_4))

    # 中下-中：端点分组卡 (y=395~640, 320x245 at x=580)
    parts.append(rect(580, 395, 320, 245, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(600, 425, "18 REST 端点", size=20, fill=GOLD, weight="700"))
    endpoints = [
        (460, "▸ 数据查询    7"),
        (490, "▸ 路径规划    4"),
        (520, "▸ 站点管理    4"),
        (550, "▸ 网络分析    2"),
        (580, "▸ 健康        1"),
    ]
    for ey, s in endpoints:
        parts.append(text(600, ey, s, size=16, fill=TEXT_2))
    parts.append(text(600, 620, "std::shared_mutex g_state_mutex", size=14, fill=GOLD, font=MONO))

    # 中下-右：并发模型 (y=395~640, 320x245 at x=920)
    parts.append(rect(920, 395, 320, 245, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(940, 425, "并发（shared_mutex）", size=20, fill=GOLD, weight="700"))
    parts.append(text(940, 470, "读接口 → shared_lock", size=18, fill=GOLD, weight="700"))
    for i, s in enumerate(["· 路径规划", "· 数据查询", "· 网络分析"]):
        parts.append(text(960, 495 + i * 20, s, size=14, fill=TEXT_3))
    parts.append(text(940, 560, "写接口 → unique_lock", size=18, fill=GOLD, weight="700"))
    for i, s in enumerate(["· 站点开关", "· 批量/恢复"]):
        parts.append(text(960, 585 + i * 20, s, size=14, fill=TEXT_3))

    # 底部
    parts.append(text(1200, 700, "C++17 · CMake · cpp-httplib · Vanilla JS · Tailwind",
                     size=14, fill=TEXT_4, anchor="end"))

    write_slide(7, "visualization", "\n  ".join(parts))


def slide_08_tests_summary():
    parts = []
    # Header (no badge - summary page)
    parts.append(text(80, 90, "测试验证与总结", size=44, fill=TEXT_1, weight="700"))
    parts.append(line(80, 110, 1200, 110, stroke=METRO_RED, sw=3))

    # 上部左：测试矩阵 (y=175~440, 560x265 at x=60)
    parts.append(rect(60, 175, 560, 265, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 210, "测试覆盖", size=24, fill=GOLD, weight="700"))
    test_rows = [
        (250, "test_cases.cpp    41 / 41 ✅   M1-M4 + 扩展"),
        (285, "  · M1 菜单结构 · 输入验证"),
        (320, "  · M2 运营管理 · 批量更新 · 恢复"),
        (355, "  · M3 Dijkstra · Yen K-shortest"),
        (390, "  · M4 最少换乘 · Yen K-min-transfer"),
        (420, "coursework_check.cpp    53 / 53 ✅   课设要求映射"),
    ]
    for ry, s in test_rows:
        parts.append(text(80, ry, s, size=18, fill=TEXT_2))

    # 上部右：课设覆盖表 (y=175~440, 560x265 at x=660)
    parts.append(rect(660, 175, 560, 265, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(680, 210, "6 大模块覆盖", size=24, fill=GOLD, weight="700"))
    coverage = [
        (255, "数据集建设", "10 pts", "20 线路 API 抓取"),
        (285, "图拓扑",     "10 pts", "800 节点 + 换乘拆分"),
        (315, "路径算法",   "15 pts", "4 算法 + K 优"),
        (345, "运营管理",   "15 pts", "单/批量/恢复"),
        (375, "网络分析",   " 5 pts", "BFS/DFS"),
        (405, "可视化",     "—",      "Web UI + 官方配色"),
    ]
    for ry, mod, pts, note in coverage:
        parts.append(text(680, ry, mod, size=16, fill=TEXT_2))
        parts.append(text(900, ry, pts, size=16, fill=TEXT_2))
        parts.append(text(1000, ry, "✅", size=16, fill=GOLD))
        parts.append(text(1030, ry, note, size=16, fill=TEXT_3))

    # 下部左：收获 (x=60, 560x220, y=460~680)
    parts.append(rect(60, 460, 560, 220, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(80, 490, "收获", size=22, fill=GOLD, weight="700"))
    gains = [
        (525, "▸ C++ 图算法从零实现（Dijkstra · Yen · BFS · DFS）"),
        (565, "▸ REST + 并发编程实践（shared_mutex 读写锁）"),
        (605, "▸ 真实数据集端到端流水线（API → CSV → 图 → 可视化）"),
    ]
    for gy, s in gains:
        parts.append(text(80, gy, s, size=17, fill=TEXT_2))
    parts.append(text(80, 660, "github.com/Weishi-corroding/shanghai-metro-pathfinder",
                     size=14, fill=TEXT_4, font=MONO))

    # 下部右：展望 (x=660, 560x220)
    parts.append(rect(660, 460, 560, 220, fill=CARD, stroke=CARD_STROKE, sw=2, rx=10))
    parts.append(text(680, 490, "展望", size=22, fill=GOLD, weight="700"))
    future = [
        (525, "▸ 实时运营状态接入"),
        (555, "▸ 移动端 / PWA"),
        (585, "▸ 多目标（票价 + 拥挤度）"),
        (615, "▸ 历史行程学习推荐"),
    ]
    for fy, s in future:
        parts.append(text(680, fy, s, size=17, fill=TEXT_2))
    parts.append(text(1200, 660, "东华大学 · 数据结构课设 · 2026-07 · v2.0.0",
                     size=14, fill=TEXT_4, font=MONO, anchor="end"))

    write_slide(8, "tests_summary", "\n  ".join(parts))


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
