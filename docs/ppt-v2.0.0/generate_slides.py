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
    pass  # Task 2

def slide_03_dataset_graph():
    pass  # Task 2

def slide_04_algorithms():
    pass  # Task 2

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
