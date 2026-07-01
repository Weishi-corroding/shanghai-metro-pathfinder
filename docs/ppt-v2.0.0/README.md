# 答辩 PPT v2.0.0（小组答辩版）

**成品**：`答辩PPT-v2.0.0.pptx`（8 页，1280×720，深蓝 + 上海地铁真实线路配色）

**设计规范**：`../superpowers/specs/2026-07-01-ppt-v2.0.0-group-defense-design.md`

**与 v1.0.0 的关系**：并列版本，不覆盖 `docs/ppt-v1.0.0/`。v2.0.0 面向课设 6 大模块均衡覆盖（把 v1.0.0 的 2 个算法页压缩为 1 页，腾出运营管理和网络分析各 1 页）。

## 页面清单

| 页 | 主题 | 对应课设模块 |
|---|---|---|
| 1 | 封面 | — |
| 2 | 项目概览 | — |
| 3 | 数据集建设 & 图建模 | 数据集 10 + 图拓扑 10 |
| 4 | 路径算法（Dijkstra + Yen + MinTransfer） | 路径算法 15 |
| 5 | 运营管理（M2） | 运营管理 15 |
| 6 | 网络分析（BFS/DFS） | 网络分析 5 |
| 7 | 可视化与工程（前后端 + 并发） | 可视化 + 端到端 |
| 8 | 测试验证与总结 | 41 测试 · 53 课设检查 |

## 如何重新生成

构建目录在 `artifacts/ppt-v2.0.0-build/`（git 忽略）：

```bash
# 1. 编辑 generate_slides.py 后重跑
cd artifacts/ppt-v2.0.0-build
python generate_slides.py
cd -

# 2. ppt-master 后处理管道
uvx ppt-master finalize-svg artifacts/ppt-v2.0.0-build
uvx ppt-master svg-to-pptx artifacts/ppt-v2.0.0-build

# 3. 同步交付物到 docs/ppt-v2.0.0/
cp artifacts/ppt-v2.0.0-build/generate_slides.py docs/ppt-v2.0.0/generate_slides.py
cp artifacts/ppt-v2.0.0-build/svg_output/*.svg docs/ppt-v2.0.0/svg_output/
LATEST=$(ls -t artifacts/ppt-v2.0.0-build/exports/*.pptx | head -1)
cp "$LATEST" docs/ppt-v2.0.0/答辩PPT-v2.0.0.pptx
```

如果 `artifacts/ppt-v2.0.0-build/` 缺失，从零重建：

```bash
uvx ppt-master project init metro_defense_v200 --format ppt169 --dir artifacts/ppt-v2.0.0-build
cp metroView.jpg artifacts/ppt-v2.0.0-build/images/
cp docs/ppt-v2.0.0/generate_slides.py artifacts/ppt-v2.0.0-build/
# 然后执行上面 1-3 步
```

## 关键数字溯源

| 陈述 | 来源 |
|---|---|
| 20 线路 · 530+ 物理站 | `python/data/Station.csv` |
| 800+ 图节点 · 1300+ 有向边 · 278 换乘边 | `/api/graph/summary` 实测 |
| 41 项测试通过 | `cpp/tests/test_cases.cpp` |
| 53 项课设检查通过 | `cpp/tests/coursework_check.cpp` |
| 18 REST 端点 | `grep -cE "svr\.(Get\|Post)" cpp/backend/server.cpp` |
| ~3,100 C++ 行 | 项目总代码统计（CLAUDE.md） |
| std::shared_mutex g_state_mutex | `cpp/backend/server.cpp:49` |
| 4 号线内/外圈 | `PathResult::line4_dirs` |
| 换乘边 t=5 | `cpp/src/build_dataset.cpp` |
| 换乘计数三规则 | `CLAUDE.md` "Transfer-counting semantics" |

## 现场演示建议

- 第 3 页人民广场三节点拆分示例是理解图建模的最快切入点
- 第 4 页换乘计数三规则是 v1.0.0 修复的核心 bug（起点、中途、终点三条语义）
- 第 6 页 BFS/DFS 可以配合前端"网络分析"标签页现场演示
- 第 7 页架构图对应 `cpp/backend/server.cpp` 与 `cpp/backend/static/app.js`
- 第 8 页课设覆盖表可对照 `cpp/tests/coursework_check.cpp` 现场跑

## UI 截图说明

`images/metroView.jpg` 是 Legacy D3 地图版截图。当前主线前端为极简卡片版（v1.0.0 交付一致）。若需替换：

```bash
# 启动服务器（终端 A）
cd cpp/build
./metro_server_s.exe --data ../../python/data --port 8080

# 浏览器打开 http://localhost:8080 截图，覆盖 docs/ppt-v2.0.0/images/metroView.jpg
# 然后重跑生成脚本
```
