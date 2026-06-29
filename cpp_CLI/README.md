# cpp_CLI — 最小可行命令行版

上海地铁线路查询系统的精简 C++17 实现，**只有命令行交互**，覆盖课设要求中 M1-M4 的全部功能。

## 与 `cpp/` 的关系

| 项目 | `cpp/` | `cpp_CLI/`（本目录） |
|---|---|---|
| 模块数 | 8 个 | 4 个（csv / station / graph / pathfinder）+ menu&main 合一 |
| 源码行数 | ~3100 | ~1050 |
| 依赖 | C++17 标准库 + httplib + nlohmann/json | **仅 C++17 标准库** |
| 命令行入口 | ✓ | ✓ |
| HTTP 服务 + Web 前端 | ✓ | ✗ |
| 网络分析(BFS/DFS) | 独立模块 | 折叠在 pathfinder 中 |
| build_dataset 工具 | ✓ | ✗（直接读 `python/data/`） |
| 测试套件 | 41 项 + 53 项课设要点 | （无） |

定位：用于课设最低验收的可独立交付版本。复用 `python/data/` 中已经生成好的 4 个 CSV，因此不需要重跑数据管线。

## 功能清单

- M1 控制台一/二级菜单 + 输入异常防护（非数字、浮点、负数、越界自动回正）
- M2 站点/运营状态管理：CSV 批量更新、手工切换、显示关闭站点、初始状态恢复、按线路列出站点、关闭波及范围（BFS）、站点查询、连通分量检测（DFS）
- M3 最短时间路径：Dijkstra + Yen K-最短，含换乘 5 分钟惩罚、自动规避关闭站点、4 号线内外圈方向标记
- M4 最少换乘路径：(transfers, time) 字典序双权重 Dijkstra + Yen K
- 起终点模糊匹配（输入"上海体"自动列出"上海体育馆/上海体育场"等）

## 数据要求

复用同仓库 `python/data/` 下：
- `Station.csv` — 525 个站点
- `Edge.csv` — 1226 条有向边
- `Station_init.csv` — 恢复初始用
- `update_station_status.csv` — 批量更新样本

启动时按 `../python/data` → `python/data` → `../../python/data` → `data` 顺序自动探测，也可命令行 `--data <path>` 显式指定。

## 编译

```bash
# 方式 A：CMake（推荐）
cd cpp_CLI && mkdir -p build && cd build
cmake .. && cmake --build .

# 方式 B：单条 g++（MinGW-w64 / clang++）
cd cpp_CLI
bash build.sh

# 方式 C：手动一行
g++ -std=c++17 -O2 -Wall -I include \
    src/csv.cpp src/station.cpp src/graph.cpp src/pathfinder.cpp src/main.cpp \
    -o build/metro_cli.exe
```

## 运行

```bash
cd cpp_CLI
./build/metro_cli            # 自动定位 ../python/data
./build/metro_cli --data D:/Code/metro/python/data    # 显式数据目录
```

启动样例：
```
[OK] 数据目录: ../python/data
      站点数: 525  图节点数: 759  边数: 1226

==== 地铁路径规划系统 ====
1. 线路站点信息/运营状态管理
2. 所需时间最短路径规划
3. 所需换乘次数最少路径规划
4. 退出系统
请输入选项编号:
```

## 文件结构

```
cpp_CLI/
├── CMakeLists.txt
├── build.sh
├── README.md
├── include/
│   ├── csv.hpp          # 30 行：CSV 读写 + trim
│   ├── station.hpp      # 50 行：Station + StationManager 接口
│   ├── graph.hpp        # 40 行：Edge + Graph 接口
│   └── pathfinder.hpp   # 60 行：PathResult + pf 命名空间
└── src/
    ├── csv.cpp          # 90 行：BOM 处理、引号转义、CRLF
    ├── station.cpp      # 170 行：加载/保存/索引/批量更新
    ├── graph.cpp        # 60 行：邻接表 + 关闭站点过滤
    ├── pathfinder.cpp   # 440 行：Dijkstra/Yen/BFS/DFS/format
    └── main.cpp         # 280 行：菜单循环 + 模糊选站
```

## 与课设要求映射

| 课设评分项 | 实现位置 |
|---|---|
| 数据集建设 (10) | 直接读 `python/data/`，CSV 解析在 `csv.cpp` |
| 图拓扑构建 (10) | `graph.cpp`，换乘节点已在数据集中拆分 |
| 路径规划算法 (15) | `pathfinder.cpp`：`dijk_time`/`dijk_xfr` + Yen |
| 运营管理 (15) | `station.cpp` + `main.cpp` 子菜单 1 |
| 网络分析 (5) | `pathfinder.cpp`: `affected_area` / `component_count` |
| 规范性与稳定性 (5) | `prompt_int` / `pick_station` + 异常捕获 |
