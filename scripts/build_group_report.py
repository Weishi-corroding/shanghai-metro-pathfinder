# -*- coding: utf-8 -*-
"""
基于《小组报告模板.docx》用 Word COM 生成中文版《小组报告.docx》。

策略：
  - 以模板为基础另存为新文件（模板与现有"正式"报告均不改动）。
  - 删除模板中的 8 条批注（Comments）与红色流程图指导段。
  - 封面/目录区域就地编辑（保留 TOC 域），表格逐单元格替换内容（保留表头与边框）。
  - 表与表之间的正文整段重建，使用内置样式常量保证字体/字号/加粗/颜色与模板一致。
  - 最后刷新 TOC 域，目录自动生成页码。

运行：python scripts/build_group_report.py
"""
import os
import sys

import win32com.client as win32

# ---- WdBuiltinStyle 常量（与语言无关）----
S_N = -1    # Normal 正文
S_H1 = -2   # Heading 1
S_H2 = -3   # Heading 2
S_H3 = -4   # Heading 3
S_LP = -1   # 列表项统一用 Normal 正文（-63 在本机映射为 Title 会污染目录）

WD_COLLAPSE_END = 0
WD_FORMAT_DOCX = 16  # wdFormatDocumentDefault (.docx)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "docs", "课设要求", "小组报告模板.docx")
OUTPUT = os.path.join(ROOT, "docs", "小组报告.docx")


def code(lines):
    """把多行代码转成 (Normal, line) 列表。"""
    return [(S_N, ln) for ln in lines]


# ====================== 内容定义 ======================

# 封面成员表（保留表头“姓名|学号|贡献度”，仅填数据行）
MEMBERS = [
    ["张三", "060******", "1.1"],
    ["李四", "060******", "1.0"],
    ["钱五", "060******", "0.95"],
    ["王六", "060******", "0.95"],
    ["", "（总计）", "4"],
]

# 任务完成情况表（保留表头“任务序号|任务名称|完成情况”）
TASKS = [
    ["1", "基本功能——线路信息输入", "√"],
    ["2", "基本功能——换乘站信息输入", "√"],
    ["3", "基本功能——线路信息修改", "√"],
    ["4", "基本功能——线路查询功能", "√"],
    ["5", "基本功能——路线查询功能（最短时间）", "√"],
    ["6", "基本功能——路线查询功能（最少换乘）", "√"],
    ["7", "基本功能——用户界面（控制台+Web）", "√"],
    ["8", "进阶功能——K条最短路径查询", "√"],
    ["9", "进阶功能——K条最少换乘查询", "√"],
    ["10", "进阶功能——站点状态管理（开/关/批量）", "√"],
    ["11", "进阶功能——网络分析（BFS+DFS）", "√"],
    ["12", "进阶功能——HTTP REST API与Web可视化", "√"],
]

# 交互过程表（保留表头“轮次|提问|回复|思考及行动”）
INTERACT_DESIGN = [
    ["1", "系统需要哪些模块、各模块职责与调用关系？",
     "建议划分为CSV、站点、图、路径规划、网络分析5个核心模块，并说明依赖关系。",
     "确认5模块架构，补充utils与HTTP服务层，明确各模块单一职责。"],
]
INTERACT_CODE = [
    ["1", "实现CSV读写模块（UTF-8 BOM/引号/CRLF）",
     "Reader用状态机解析引号字段，Writer打开时自动写BOM", "创建csv.hpp与csv.cpp"],
    ["2", "实现站点管理（LLNN编号/模糊查询/批量更新）",
     "三索引设计by_id/by_line/name_index", "batch按“名称+线路”匹配，restore用Station_init.csv"],
    ["3", "实现图结构（邻接表/换乘边/边填充）",
     "unordered_map邻接表，neighbors()按值返回并过滤关闭站", "理解fill_missing与remove_loop_closure"],
    ["4", "实现Dijkstra最短时间（优先队列最小堆）",
     "TimeWeight自然operator<，std::greater<>构成最小堆", "PredecessorInfo按值存Edge，rebuild_path处理两种失败"],
    ["5", "实现Yen K最短（K=3，spur-path与去重）",
     "以模板函数yen_k复用同一框架", "去重纳入线路序列，验证总时间单调不减"],
    ["6", "实现最少换乘（二维权重）",
     "TransferWeight(transfers,time)字典序比较，状态(node,line)", "二维状态是关键，首站上车不计换乘"],
    ["7", "实现网络分析（BFS受影响/DFS连通分量）",
     "BFS换乘边不增深度，DFS统计连通分量", "换乘边不计深度符合关站影响的真实语义"],
    ["8", "实现控制台菜单与Web服务（16端点）",
     "菜单分发+httplib/json，读写锁并发安全", "读路由shared_lock，写路由unique_lock"],
]
INTERACT_TEST = [
    ["1", "编写41项测试（M1-M4+扩展），运行后发现换乘计数异常",
     "用例覆盖可达性/换乘/边界/网络分析", "定位rebuild_path预设line_trace导致首站误计一次换乘"],
    ["2", "修复换乘计数语义并统一收尾换乘处理",
     "不预设line_trace；收尾换乘与首站上车均不计数", "人民广场→陆家嘴=0次，莘庄→陆家嘴=1次"],
    ["3", "修复批量更新计数与连续换乘标记折叠",
     "计数改为按站点统计；连续--[换乘]--折叠为一个", "全部41项测试通过，核心功能100%"],
]

# 7 张测试用例表（保留表头“序号|测试目的|输入数据|期望结果|实际结果|结论”）
TEST_M1 = [
    ["1", "主菜单四大功能结构", "启动程序查看主菜单", "显示路径规划/运营管理/网络分析等功能", "显示完整菜单", "成功"],
    ["2", "非法菜单输入校验", "输入越界数字或非数字", "提示无效并要求重新输入", "正确拦截非法输入", "成功"],
]
TEST_M2 = [
    ["1", "CSV批量更新执行", "导入update_station_status.csv", "匹配的站点状态被更新", "updated>0", "成功"],
    ["2", "未注册站点自动跳过", "含非法站名的批量数据", "跳过非法行且不报错", "正确跳过", "成功"],
    ["3", "手动关闭/开启漕宝路(1号线)", "先关闭后开启该站", "状态在closed/open间正确切换", "切换正确", "成功"],
    ["4", "关闭列表动态更新", "全开时查询、关闭某站后再查询", "全开时为空、关闭后含该站", "列表正确", "成功"],
    ["5", "恢复初始状态", "调用restore_initial", "所有站点恢复为初始open状态", "恢复成功", "成功"],
    ["6", "线路信息查询(1号线)", "查询1号线全部站点", "共28站，首站莘庄、末站富锦路", "数量与首末站正确", "成功"],
    ["7", "换乘站信息(漕宝路)", "查询漕宝路换乘信息", "包含1号线与12号线换乘", "含12号线", "成功"],
]
TEST_M3_1 = [
    ["1", "跨线可达性", "莘庄(0101)→人民广场", "返回有效可达路径", "valid=true", "成功"],
    ["2", "同线0换乘", "莘庄→人民广场", "换乘次数为0", "transfer=0", "成功"],
    ["3", "换乘站起点计数", "人民广场(换乘站)出发", "首站上车不计换乘", "0次", "成功"],
    ["4", "一次换乘计数", "莘庄(0101)→陆家嘴(0217)", "中途换乘1次", "1次", "成功"],
    ["5", "起终点相同", "莘庄→莘庄", "总时间为0", "time=0", "成功"],
    ["6", "绕过关闭站点", "关闭途经站后查询", "路径自动绕开该站", "已绕过", "成功"],
    ["7", "关闭起点拒绝", "起点站被关闭", "返回无效结果", "valid=false", "成功"],
]
TEST_M3_2 = [
    ["1", "返回K=3条路径", "上海火车站→虹桥火车站, K=3", "恰返回3条路径", "size=3", "成功"],
    ["2", "时间单调不减", "同上", "time1≤time2≤time3", "单调递增", "成功"],
    ["3", "路径1无环", "检查路径1节点", "无重复节点、无死循环", "无环", "成功"],
    ["4", "路径状态有效", "检查3条路径", "均为有效路径", "全部valid", "成功"],
]
TEST_M4_1 = [
    ["1", "跨线可达", "上海体育场→江浦公园", "返回有效路径", "valid=true", "成功"],
    ["2", "换乘次数≥1", "同上", "至少1次换乘", "≥1", "成功"],
    ["3", "同线0换乘", "莘庄→人民广场", "0次换乘", "0次", "成功"],
    ["4", "换乘站终点计数", "终点为换乘站", "到站不计换乘", "0次", "成功"],
    ["5", "起终点相同", "莘庄→莘庄", "总时间0", "time=0", "成功"],
]
TEST_M4_2 = [
    ["1", "返回3条路径", "指定起终点, K=3", "恰返回3条", "size=3", "成功"],
    ["2", "换乘次数不减", "同上", "xfer1≤xfer2≤xfer3", "单调", "成功"],
    ["3", "路径有效", "检查3条路径", "均valid", "有效", "成功"],
    ["4", "时间次序合理", "同换乘次数内比较", "时间不劣化", "合理", "成功"],
]
TEST_NET = [
    ["1", "受影响区域非空", "关闭人民广场, 2阶BFS", "返回受影响站点集合", "非空", "成功"],
    ["2", "连通分量计数", "对全网做DFS", "连通分量数≥1", "≥1", "成功"],
    ["3", "主连通分量", "检查最大连通分量", "覆盖绝大多数站点", "高度连通", "成功"],
]


def region_b():
    return [
        (S_H1, "3 设计报告"),
        (S_H2, "3.1、问题描述"),
        (S_N, "上海地铁是世界上规模最大、运营最繁忙的城市轨道交通系统之一，目前已开通运营线路20条（含1—18号线、浦江线、磁浮线），车站约530座。每条线路上相邻车站之间的通行时间各不相同，不同线路之间通过换乘站相互连通。"),
        (S_N, "本项目的目标是构建一个“上海地铁路径规划与运营管理系统”，在约530个物理车站、换乘拆分后约800个图节点、约1300条有向边的网络上，实现以下功能："),
        (S_N, "（1）最短时间路径查询（Dijkstra算法）；"),
        (S_N, "（2）K条最短时间路径查询（Yen算法，K=3）；"),
        (S_N, "（3）最少换乘路径查询（按换乘次数、时间二维权重）；"),
        (S_N, "（4）K条最少换乘路径查询；"),
        (S_N, "（5）站点运营状态管理（关闭/开启站点、CSV批量更新、状态恢复）；"),
        (S_N, "（6）网络分析（受影响区域BFS、连通分量DFS）；"),
        (S_N, "（7）控制台与Web两套用户界面（含HTTP REST API与可视化页面）。"),
        (S_H2, "3.2、概要"),
        (S_N, "整个项目开发过程包含三个步骤："),
        (S_N, "（1）功能模块设计"),
        (S_N, "功能模块设计阶段包含1轮交互，交互过程概述如下："),
        (S_N, "表2 功能模块设计交互过程"),
    ]


def region_c():
    return [
        (S_N, "（2）代码实现"),
        (S_N, "代码实现共包含8轮交互，交互过程概述如下："),
        (S_N, "表3 代码实现交互过程"),
    ]


def region_d():
    return [
        (S_N, "（3）测试与调试"),
        (S_N, "测试与调试阶段包含3轮交互，交互过程概述如下："),
        (S_N, "表4 测试与调试阶段交互过程"),
    ]


def region_e():
    items = []
    # 3.3 功能模块设计
    items += [
        (S_H2, "3.3、功能模块设计"),
        (S_N, "为了开发整个系统，我们首先需要厘清系统包含哪些模块、每个模块负责什么、它们之间如何相互调用。我们向Copilot提问如下："),
        (S_N, "【提问】：我需要用C++开发一个上海地铁路径规划与运营管理系统。系统需支持：(1)20条线路、换乘拆分后约800个图节点、约1300条有向边的图数据结构；(2)Dijkstra最短时间与Yen K最短路径；(3)最少换乘与K最少换乘；(4)站点关闭/开启与CSV批量更新；(5)受影响区域与连通分量等网络分析。请分析该程序应划分为哪几个模块，各完成什么功能，相互如何调用。"),
        (S_N, "【回复】：这是一个综合性的地铁路径规划系统，涉及数据结构、图论算法、文件IO与用户界面。建议划分为以下模块："),
        (S_LP, "1. CSV数据模块：负责CSV文件读写，处理UTF-8 BOM编码，包含Reader与Writer两个核心类。"),
        (S_LP, "2. 站点管理模块：负责站点注册、查询与运营状态管理；同一物理站点在不同线路上拆分为不同节点。"),
        (S_LP, "3. 图结构模块：以邻接表存储地铁网络，节点为拆分后的站点节点，边包括线路段与换乘边。"),
        (S_LP, "4. 路径规划模块：实现Dijkstra与Yen算法，支持最短时间与最少换乘两种权重。"),
        (S_LP, "5. 网络分析模块：实现BFS受影响区域查询与DFS连通分量计数。"),
        (S_N, "这些模块的相互调用关系如下："),
        (S_LP, "• 路径规划模块调用图结构模块与站点管理模块；"),
        (S_LP, "• 网络分析模块调用图结构模块与站点管理模块；"),
        (S_LP, "• 图结构模块在构建时依赖CSV数据模块读取边数据；"),
        (S_LP, "• 站点管理模块依赖CSV数据模块读取站点数据。"),
        (S_N, "【说明】：根据以上回复，我们确认了5个核心模块，并补充了utils辅助模块与HTTP服务层。最终系统架构包含csv、station、graph、pathfinder、network_analysis、utils等模块，职责清晰、依赖单向。系统功能模块设计如下图所示："),
        (S_N, "图1  系统功能模块设计"),
    ]
    # 3.4 代码实现
    items += [
        (S_H2, "3.4、代码实现"),
        (S_N, "由于功能模块较多，无法通过一次提问实现全部功能，下面通过多次提问逐步细化和实现。"),
        (S_N, "【提问1】：请实现C++ CSV读写模块（csv.hpp/csv.cpp）：(1)读取UTF-8 BOM并自动跳过；(2)写入时自动加BOM；(3)支持带引号字段与转义引号；(4)兼容Windows CRLF。"),
        (S_N, "【回复1】：Reader使用NORMAL/QUOTED/AFTER_QUOTE状态机解析引号字段，Writer打开时自动写入BOM（\\xEF\\xBB\\xBF）以兼容中文Excel。"),
        (S_N, "【说明】：理解了状态机设计，将代码创建为csv.hpp与csv.cpp。关键结构如下："),
    ]
    items += code([
        "// csv.hpp（关键结构）",
        "namespace metro::csv {",
        "class Reader {",
        "  bool open(const std::string& path);",
        "  std::vector<std::string> header();",
        "  std::vector<std::map<std::string,std::string>> read_all();",
        "  private: void skip_bom();   // 跳过 \\xEF\\xBB\\xBF",
        "  std::ifstream fin_;",
        "};",
        "class Writer {",
        "  bool open(const std::string& path);  // 自动写BOM",
        "  void write_header(const std::vector<std::string>&);",
        "  void write_row(const std::vector<std::string>&);",
        "};",
        "}",
    ])
    items += [
        (S_N, "【提问2】：请实现地铁图结构（graph.hpp/cpp）：邻接表存储，节点ID为字符串（如\"0101\"）；有向边含目标、线路、时间、方向；neighbors()过滤关闭站点但保留换乘边。"),
        (S_N, "【回复2】：Edge含to/line/time/direction四个字段；Graph使用unordered_map<string,vector<Edge>>存储邻接表；neighbors()按值返回并过滤关闭的目标站。"),
        (S_N, "【说明】：理解neighbors()过滤关闭站但允许换乘边；fill_missing_adjacent_edges()修补缺失的反向边；remove_loop_closure_edges()移除环线（如4号线）的伪闭合边。"),
    ]
    items += code([
        "// graph.hpp（关键结构）",
        "struct Edge {",
        "  std::string to;        // 目标节点ID",
        "  std::string line;      // 线路名（“换乘”表示换乘边）",
        "  int time;              // 时间/分钟（换乘边固定5）",
        "  std::string direction; // 方向标签（仅4号线内/外圈）",
        "};",
        "class Graph {",
        "  std::vector<Edge> neighbors(const std::string& id,",
        "                              const StationManager& mgr) const;",
        "  private:",
        "  std::unordered_map<std::string, std::vector<Edge>> adj_;",
        "};",
    ])
    items += [
        (S_N, "【提问3】：请实现Dijkstra最短时间算法：优先队列最小堆；边权为时间；换乘边固定5分钟；支持关闭站过滤；返回含节点序列、总时间、换乘次数的PathResult。"),
        (S_N, "【回复3】：TimeWeight用operator<实现自然比较（越小越好），优先队列用std::greater<TimeWeight>构成最小堆；rebuild_path从终点回溯构建路径。"),
        (S_N, "【说明】：三处关键细节：(1)权重比较绝不可反向（曾因反向导致非最优解）；(2)PredecessorInfo按值存储Edge，避免指向临时vector的悬垂指针；(3)rebuild_path需处理起点prev为空与环检测两种失败情形。算法流程如下图所示："),
        (S_N, "图2  Dijkstra最短时间算法流程图"),
    ]
    items += code([
        "// TimeWeight：自然 operator<（越小越好）",
        "struct TimeWeight {",
        "  int time;",
        "  bool operator<(const TimeWeight& o) const { return time < o.time; }",
        "};",
        "std::priority_queue<State, std::vector<State>, std::greater<State>> pq;",
        "PathResult dijkstra_shortest_time(",
        "    const std::string& src, const std::string& dst,",
        "    const Graph&, const StationManager&);",
    ])
    items += [
        (S_N, "【提问4】：请实现Yen K最短路径（K=3）：基于Dijkstra的spur-path方法；路径去重；结果按总时间单调递增排序。"),
        (S_N, "【回复4】：以模板函数实现，TimeWeight与TransferWeight共用同一算法框架：A[0]为Dijkstra最短路；对每条已知路径的每个spur节点，移除相关边/节点求候选路径并入堆排序。"),
        (S_N, "【说明】：模板函数避免了约50行重复代码；去重时将线路序列纳入键，修复了同站不同线导致的重复路径问题。测试验证K=3时total_time单调不减。"),
    ]
    items += code([
        "template<typename Weight>",
        "std::vector<PathResult> yen_k(",
        "    const Graph& g, const StationManager& mgr,",
        "    const std::string& start, const std::string& end, int k) {",
        "  std::vector<PathResult> A;   // A[0] = Dijkstra 最短路",
        "  // 对每个 spur 节点：root+spur -> 候选路径 -> 最小堆",
        "  return A;",
        "}",
    ])
    items += [
        (S_N, "【提问5】：请实现最少换乘规划：TransferWeight按(换乘次数,时间)字典序比较；状态为(节点,线路)二维。"),
        (S_N, "【回复5】：TransferWeight先比较换乘次数、相等时再比较时间；状态空间为(node,line)二维——同一节点经由不同线路到达，其换乘代价不同。"),
        (S_N, "【说明】：二维状态空间是最少换乘的关键；并明确首站上车与终点下车均不计为换乘，符合乘客的实际语义。"),
    ]
    items += code([
        "struct TransferWeight {",
        "  int transfers, time;",
        "  bool operator<(const TransferWeight& o) const {",
        "    if (transfers != o.transfers) return transfers < o.transfers;",
        "    return time < o.time;",
        "  }",
        "};",
        "PathResult dijkstra_min_transfers(",
        "    const std::string& src, const std::string& dst,",
        "    const Graph&, const StationManager&);",
    ])
    items += [
        (S_N, "【提问6】：请实现网络分析：affected_area用BFS（K阶邻居），count_components用DFS统计连通分量。"),
        (S_N, "【回复6】：BFS带深度跟踪，换乘边不增加深度；DFS遍历统计连通分量数量。"),
        (S_N, "【说明】：换乘边不计入深度反映了真实语义——某站关闭的影响沿物理相邻车站传播，而非沿换乘关系扩散。"),
    ]
    items += code([
        "namespace metro::analysis {",
        "std::vector<std::string> affected_area(",
        "    const Graph&, const StationManager&,",
        "    const std::string& center, int k);   // BFS K阶邻居",
        "std::vector<std::vector<std::string>> count_components(",
        "    const Graph&, const StationManager&); // DFS 连通分量",
        "}",
    ])
    items += [
        (S_N, "【提问7】：请实现控制台菜单与Web服务：菜单按4大功能分发；HTTP服务基于httplib+nlohmann/json提供16个端点，并保证读写并发安全。"),
        (S_N, "【回复7】：菜单将操作分发到pathfinder/analysis/StationManager；服务端用std::shared_mutex，读路由取shared_lock、写路由取unique_lock。"),
        (S_N, "【说明】：pathfinder函数接受const引用，天然适配shared_lock并发读；StationManager::set_status需unique_lock独占。前端为离线可用的纯REST页面。"),
    ]
    # 3.5 使用示例
    items += [
        (S_H2, "3.5、使用示例"),
        (S_N, "根据用户界面，依次演示系统主要功能的运行效果（运行截图见下，并加小标题说明）。"),
        (S_N, "（1）最短时间路径查询"),
        (S_N, "输入起点“莘庄”(0101)、终点“陆家嘴”(0217)，查询最短时间路径，结果：总时间约28分钟，换乘1次，线路1号线→2号线。"),
        (S_N, "图3  最短时间路径查询结果"),
        (S_N, "（2）K条最短时间路径查询"),
        (S_N, "输入起点“上海火车站”、终点“虹桥火车站”，K=3，返回3条路径，总时间单调递增。"),
        (S_N, "图4  K条最短路径查询结果"),
        (S_N, "（3）最少换乘路径查询"),
        (S_N, "输入起点“莘庄”、终点“浦东国际机场”，返回最少换乘路径及对应总时间。"),
        (S_N, "图5  最少换乘路径查询结果"),
        (S_N, "（4）站点运营管理"),
        (S_N, "关闭站点“人民广场”后再次查询，路径自动绕过该站。"),
        (S_N, "图6  关闭站点后的绕行路径"),
        (S_N, "（5）网络分析——受影响区域"),
        (S_N, "关闭“人民广场”后查询2阶受影响区域，列出受影响站点；并可查询全网连通分量。"),
        (S_N, "图7  受影响区域分析结果"),
    ]
    # 3.6 测试与调试 + 3.6.1（M1）引导
    items += [
        (S_H2, "3.6、测试与调试"),
        (S_N, "本项目使用自定义轻量测试框架编写了41项自动化测试用例，覆盖M1—M4模块及网络分析扩展功能。下面按测试类别分别说明。"),
        (S_H3, "3.6.1 M1 菜单结构与输入校验测试"),
        (S_N, "针对主菜单结构与非法输入校验，设计如下测试用例："),
        (S_N, "表5  菜单与输入校验测试用例"),
    ]
    return items


REGION_F = [
    (S_H3, "3.6.2 M2 运营管理模块测试"),
    (S_N, "针对站点状态管理、CSV批量更新、状态恢复与线路/换乘信息查询，设计如下测试用例："),
    (S_N, "表6  运营管理测试用例"),
]
REGION_G = [
    (S_H3, "3.6.3 M3-1 Dijkstra最短时间路径测试"),
    (S_N, "验证最短时间路径的可达性、换乘计数与边界情况："),
    (S_N, "表7  最短时间路径测试用例"),
]
REGION_H = [
    (S_H3, "3.6.4 M3-2 Yen K最短时间路径测试"),
    (S_N, "验证K=3时返回路径的数量、时间单调性与无环性："),
    (S_N, "表8  Yen K最短路径测试用例"),
]
REGION_I = [
    (S_H3, "3.6.5 M4-1 最少换乘路径测试"),
    (S_N, "验证最少换乘路径的换乘次数与二维权重比较的正确性："),
    (S_N, "表9  最少换乘路径测试用例"),
]
REGION_J = [
    (S_H3, "3.6.6 M4-2 Yen K最少换乘路径测试"),
    (S_N, "验证K条最少换乘路径的换乘次数单调不减："),
    (S_N, "表10  Yen K最少换乘测试用例"),
]
REGION_K = [
    (S_H3, "3.6.7 网络分析（BFS/DFS）测试"),
    (S_N, "验证受影响区域BFS与连通分量DFS分析功能："),
    (S_N, "表11  网络分析测试用例"),
]
REGION_L = [
    (S_N, "综上，41项自动化测试用例全部通过，核心路径规划功能达到100%通过率，满足验收标准。"),
    (S_H1, "4 体会与感想"),
    (S_N, "经过本次课程设计，我们对数据结构课程的核心算法有了更深入的理解。Dijkstra算法和Yen算法在课本上只是理论描述，通过实际编码实现，我们深刻体会到了优先队列优化、路径回溯、权重比较等关键细节的重要性。"),
    (S_N, "在实现过程中，我们遇到了几个比较棘手的问题：(1)换乘站拆分导致图节点数膨胀到物理站的约1.5倍，增加了图构建的复杂度；(2)换乘计数的语义问题——从换乘站上车不应计数、到达终点下车也不应计数，这需要精心设计rebuild_path的回溯逻辑；(3)权重比较方向一旦写反就会得到非最优解，这类bug只能通过严谨的测试用例发现。"),
    (S_N, "通过使用AI辅助编程，我们发现它能够快速生成算法框架代码，但细节的正确性仍需人工审查。例如AI最初生成的换乘计数逻辑在“从换乘站出发”和“到达换乘站终点”两处存在边界错误，这让我们认识到：AI是强大的工具，但不能替代对算法本身的理解。"),
    (S_N, "在团队分工方面，我们分别负责图结构模块、路径规划模块、网络分析模块与前端界面，通过Git进行代码管理，定期的代码审查帮助我们发现并修复了多个潜在bug。总的来说，这次课程设计不仅锻炼了我们的编程能力，也加深了对图论算法的理解，同时让我们体验了现代软件开发中AI辅助编程的工作模式。"),
]


# ====================== COM 编辑辅助 ======================

def set_para_text(para, text):
    """替换段落文本但保留段落标记与首字符格式。"""
    r = para.Range
    r.End = r.End - 1  # 排除段落标记，避免与下一段合并
    r.Text = text


def find_para(doc, contains):
    for p in doc.Paragraphs:
        if contains in p.Range.Text:
            return p
    return None


def fill_table(doc, com_idx, data_rows):
    """保留表头(第1行)，用 data_rows 替换其余数据行，必要时增删行。"""
    t = doc.Tables(com_idx)
    need = 1 + len(data_rows)
    while t.Rows.Count < need:
        t.Rows.Add()
    while t.Rows.Count > need:
        t.Rows(t.Rows.Count).Delete()
    for ri, row in enumerate(data_rows, start=2):
        for ci, val in enumerate(row, start=1):
            t.Cell(ri, ci).Range.Text = val


def insert_block(doc, pos, items):
    """在 pos 处依次插入段落，每段套用对应内置样式；返回插入块末尾位置。"""
    rng = doc.Range(pos, pos)
    for style, text in items:
        rng.InsertAfter(text + "\r")
        rng.Style = style
        rng.Collapse(WD_COLLAPSE_END)
    return rng.End


def rebuild_between(doc, k, k1, items):
    """重建第 k 与第 k1 张表之间的正文（先插入新内容，再删除旧内容，避免表合并）。"""
    pos = doc.Tables(k).Range.End
    end_new = insert_block(doc, pos, items)
    del_end = doc.Tables(k1).Range.Start
    if del_end > end_new:
        doc.Range(end_new, del_end).Delete()
    return end_new


def main():
    if not os.path.exists(TEMPLATE):
        print("模板不存在:", TEMPLATE)
        sys.exit(1)
    if os.path.exists(OUTPUT):
        os.remove(OUTPUT)

    word = win32.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(TEMPLATE)
        doc.SaveAs2(OUTPUT, FileFormat=WD_FORMAT_DOCX)

        # 1) 删除全部批注
        try:
            doc.DeleteAllComments()
        except Exception as e:
            print("删除批注:", e)

        # 2) 封面 / 正文就地编辑（保留 TOC 域）
        p = find_para(doc, "日    期")
        if p:
            set_para_text(p, "日    期： 2026年6月20日至2026年7月01日")
        p = find_para(doc, "掌握面向实际背景")
        if p:
            set_para_text(p, "掌握面向实际背景思考问题的方法。")
        p = find_para(doc, "任务完成情况介绍")
        if p:
            set_para_text(p, "任务完成情况如下表所示。")

        # 3) 填充各表格（COM 表索引 1-based）
        fill_table(doc, 1, MEMBERS)
        fill_table(doc, 2, TASKS)
        fill_table(doc, 3, INTERACT_DESIGN)
        fill_table(doc, 4, INTERACT_CODE)
        fill_table(doc, 5, INTERACT_TEST)
        fill_table(doc, 6, TEST_M1)
        fill_table(doc, 7, TEST_M2)
        fill_table(doc, 8, TEST_M3_1)
        fill_table(doc, 9, TEST_M3_2)
        fill_table(doc, 10, TEST_M4_1)
        fill_table(doc, 11, TEST_M4_2)
        fill_table(doc, 12, TEST_NET)

        # 4) 重建表间正文（自顶向下）
        rebuild_between(doc, 2, 3, region_b())
        rebuild_between(doc, 3, 4, region_c())
        rebuild_between(doc, 4, 5, region_d())
        rebuild_between(doc, 5, 6, region_e())
        rebuild_between(doc, 6, 7, REGION_F)
        rebuild_between(doc, 7, 8, REGION_G)
        rebuild_between(doc, 8, 9, REGION_H)
        rebuild_between(doc, 9, 10, REGION_I)
        rebuild_between(doc, 10, 11, REGION_J)
        rebuild_between(doc, 11, 12, REGION_K)

        # 5) 表12 之后到文末：重建结语与第4章
        last = doc.Tables(12)
        pos = last.Range.End
        end_new = insert_block(doc, pos, REGION_L)
        doc_end = doc.Content.End
        if doc_end - 1 > end_new:
            doc.Range(end_new, doc_end - 1).Delete()

        # 6) 刷新目录域（自动生成页码）
        try:
            for i in range(1, doc.TablesOfContents.Count + 1):
                doc.TablesOfContents(i).Update()
        except Exception as e:
            print("更新目录:", e)
        try:
            doc.Fields.Update()
        except Exception:
            pass
        doc.Repaginate()

        doc.Save()
        print("已生成:", OUTPUT)
    finally:
        if doc is not None:
            doc.Close()
        word.Quit()


if __name__ == "__main__":
    main()
