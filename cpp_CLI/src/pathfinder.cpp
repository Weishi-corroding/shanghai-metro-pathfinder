// pathfinder.cpp — 路径规划核心实现，对应接口见 pathfinder.hpp。
//
// 本文件提供四个对外算法 + 一个格式化函数 + 两个网络分析函数：
//   shortest_time      — M3-1  单条最短时间路径（Dijkstra）
//   k_shortest_time    — M3-2  前 K 条最短时间路径（Yen's K-Shortest Paths）
//   min_transfers      — M4-1  单条最少换乘路径（双权 Dijkstra）
//   k_min_transfers    — M4-2  前 K 条最少换乘路径（Yen + 双权）
//   format             — 路径结果的控制台格式化输出
//   affected_area      — BFS 计算关闭一个站后受波及的相邻站点
//   component_count    — DFS 计算当前开放子图的连通分量数
//
// === 关键设计（也可参考仓库根目录 CLAUDE.md "Important quirks" 节）===
//
//  ① 权值类型用"自然 operator<（越小越好）"+ std::greater<> 构造最小堆。
//     不要反过来把 operator< 改成"越小越大"——那是父项目 cpp/ 早期踩过的坑。
//
//  ② Pred（前驱记录）按"值"存边的字段，绝不存 const Edge*。
//     原因：Graph::neighbors() 返回 const& 进入 adj_ 的内部 vector；
//     若该 vector 重新分配（运行时若再 load），Edge* 会悬空。
//
//  ③ walk_back() 必须同时处理两种终止条件：
//        (a) 起点节点的 prev 为 ""（自然终止）
//        (b) 异常成环时 seen 集合检测并跳出（防御性）
//
//  ④ 最少换乘的"换乘"语义：从一条非换乘线路换到 *另一条* 非换乘线路时
//     才 +1；图中 "换乘" 边（连接同名站的两个线路节点）本身不直接累加，
//     换乘是通过下一条乘车边的 line 变化"隐式"感知的。这与乘客视角一致：
//     在站内换站台不算"骑乘新线路"，骑上之后才算。
//
//  ⑤ 4 号线内圈/外圈方向标签写在 *目标* 节点 ID 上，标签内容直接取自
//     Edge.csv 的 direction 字段（含"内"或"外"字）。

#include "pathfinder.hpp"
#include "graph.hpp"
#include "station.hpp"

#include <queue>
#include <unordered_set>
#include <unordered_map>
#include <algorithm>
#include <sstream>
#include <climits>

namespace mini::pf {

namespace {

// ============================================================================
// 权值类型（priority_queue 的 key）
// ============================================================================
// 两个权值都按"自然序：越小越好"定义 operator<；priority_queue 配
// std::greater<> 使用，得到最小堆。


struct TimeW {                      // 一维：累计通行时间（含换乘 5 min 惩罚）
    int t = 0;
    bool operator<(const TimeW& o) const { return t < o.t; }
    bool operator>(const TimeW& o) const { return t > o.t; }
};

struct XfrW {                       // 二维字典序：(换乘数, 时间)
    int x = 0, t = 0;
    bool operator<(const XfrW& o) const {
        return x != o.x ? x < o.x : t < o.t;
    }
    bool operator>(const XfrW& o) const {
        return x != o.x ? x > o.x : t > o.t;
    }
};

// ----------------------------------------------------------------------------
// 前驱记录（Predecessor）—— Dijkstra 中每个节点记下"从谁来 / 走的哪条边"。
// 注意：边字段按值存（line/dir/time/is_transfer），不存 Edge*，避免悬空。
// ----------------------------------------------------------------------------
struct Pred {
    std::string prev;       // 上一个节点 ID（起点的 prev 为 ""）
    std::string line;       // 这条入边所属线路
    std::string dir;        // 行驶方向（含"内"/"外"用于 4 号线）
    int time = 0;           // 这条入边的通行时间（分钟）
    bool is_transfer = false;
};

// ============================================================================
// 路径回溯：从 cf（came_from 映射）从终点向起点反向走，得到正序 ID 列表
// ============================================================================
// 两种正常终止条件：
//   (a) 走到起点时 prev 为空串
//   (b) cf 里没有当前节点的记录（说明已经走过 head）
// 防御性：用 seen 集合检测异常环（理论上 Dijkstra 不会形成环，但万一
// 上层逻辑改坏了 cf，至少不会进入死循环）。
std::vector<std::string> walk_back(const std::string& end,
                                   const std::unordered_map<std::string, Pred>& cf) {
    std::vector<std::string> ids;
    std::unordered_set<std::string> seen;
    std::string c = end;
    while (true) {
        if (seen.count(c)) break;          // 异常环
        seen.insert(c);
        ids.push_back(c);
        auto it = cf.find(c);
        if (it == cf.end()) break;         // 到 head
        c = it->second.prev;
        if (c.empty()) break;              // 起点
    }
    std::reverse(ids.begin(), ids.end());
    return ids;
}

// ============================================================================
// assemble —— 把节点序列还原成完整 PathResult（含累计耗时、换乘统计等）
// ============================================================================
// 为什么不直接用 Dijkstra 内部的累积值？
//   • Yen K 算法把已知子路径拼接成新候选路径，这种路径不是 Dijkstra 一次
//     找出来的，没有现成的累计值；统一在这里重算最简单。
//   • Dijkstra 出的"换乘数 x"是基于内部 node_line 跟踪的，跟乘客视角下的
//     "经历几次站台间转线"有微妙差异（见下文 line_trace 注释）；统一在
//     assemble 里按乘客视角重算最稳妥。
//
// line_trace 是"乘车段的线路序列"：只记 *非换乘* 边的发车端站点 + 线路名。
// 起点先 seed 一条（id, src.line, src.name）作为"起始所在线"。
// 然后遍历边：换乘边只累加时间，不入 line_trace；普通边把"起点侧"站点和
// 这条边的线路压入 trace。两段 trace 之间 line 不同即一次换乘。
PathResult assemble(const std::vector<std::string>& ids,
                    const Graph& g, const StationManager& m) {
    PathResult r;
    r.ids = ids;
    if (ids.empty()) { r.valid = false; r.error = "未找到可达路径。"; return r; }

    // 1) 第一遍扫描：累计总耗时 + 收集 line_trace + 4 号线方向标签
    std::vector<std::tuple<std::string, std::string, std::string>> line_trace;
    const Station* s0 = m.get(ids[0]);
    if (s0) line_trace.emplace_back(ids[0], s0->line, s0->name);

    for (size_t i = 1; i < ids.size(); ++i) {
        const Edge* e = g.get_edge(ids[i - 1], ids[i]);
        if (!e) continue;
        r.total_time += e->time;
        if (!e->is_transfer()) {
            const Station* s = m.get(ids[i - 1]);
            line_trace.emplace_back(ids[i - 1], e->line,
                                    s ? s->name : std::string());
            // 4 号线：根据边方向字段中的"内"/"外"字给目标节点贴标签
            if (e->line.find("4号线") != std::string::npos && !e->direction.empty()) {
                if (e->direction.find("内") != std::string::npos)
                    r.line4_dirs[ids[i]] = "内圈";
                else if (e->direction.find("外") != std::string::npos)
                    r.line4_dirs[ids[i]] = "外圈";
            }
        }
    }

    // 2) 第二遍扫描：line_trace 内相邻两段 line 不同则换乘 +1，记下换乘点。
    //
    // 注意：这里 *不* 把终点的线路追加到 line_trace 末尾作为哨兵。
    // 路径以"换乘"边结尾时（用户选了某条特定线路上的终点，但实际抵达
    // 是先从另一条线进站再换站台），那 5 分钟通道只是步行，乘客并未真正
    // 骑上新线路——按乘客视角不应计为换乘。5 分钟仍计入 total_time，
    // 但 transfers 计数不 +1。这与 Python 原版语义一致。
    if (!line_trace.empty()) {
        std::string cur_line = std::get<1>(line_trace[0]);
        for (size_t j = 1; j < line_trace.size(); ++j) {
            const auto& nl = std::get<1>(line_trace[j]);
            const auto& nm = std::get<2>(line_trace[j]);
            if (nl != cur_line) {
                ++r.transfers;
                if (r.transfer_at.empty() ||
                    std::get<0>(r.transfer_at.back()) != nm) {
                    r.transfer_at.emplace_back(nm, cur_line, nl);
                }
                cur_line = nl;
            }
        }
    }
    return r;
}

// ============================================================================
// guard —— 路径规划前的统一前置校验
// ============================================================================
// 处理三种边界：起终点相同 / 起点或终点关闭 / 起点终点 ID 不在 manager。
// 调用方通过查看返回值的 ids 是否非空 + valid 状态决定是否继续算法搜索。
PathResult guard(const std::string& src, const std::string& dst,
                  const StationManager& m) {
    PathResult r;
    if (src == dst) {
        r.ids = {src};
        r.error = "起点和终点相同，无需进行路径规划。";
        return r;  // valid, with single-id path
    }
    auto chk = [&](const char* who, const std::string& id) -> bool {
        const Station* s = m.get(id);
        if (s && !s->open()) {
            r.valid = false;
            r.error = std::string(who) + "：" + s->name + "(" + s->line +
                      ")已关闭，无法进行路径规划。";
            return false;
        }
        return true;
    };
    if (!chk("起点", src) || !chk("终点", dst)) return r;
    // 此时 valid=true、ids 为空 → 调用方按"通过校验，继续搜索"处理
    return r;
}

// Yen 算法用的"被屏蔽边"字符串键："a>b" 唯一标识有向边 a→b
std::string ekey(const std::string& a, const std::string& b) { return a + ">" + b; }

// ============================================================================
// 单边过滤辅助：关闭站点不可达，换乘边永远通过
// ============================================================================
// 决策细节：未知目标站（manager 里查不到 ID）被当作"开放"处理。这是
// 防御性容错——若 Edge.csv 引用了 Station.csv 没有的 ID（数据不一致），
// 与其在路径搜索时悄悄断开图，不如让算法尝试通行；最终展示层（format）
// 会用 [?id?] 占位提示用户。
bool target_open(const StationManager& m, const Edge& e) {
    if (e.is_transfer()) return true;
    const Station* t = m.get(e.to_id);
    return t == nullptr || t->open();
}

// ============================================================================
// dijk_time —— 最短时间 Dijkstra（M3）
// ============================================================================
// 经典优先队列实现，O(E log V)。rem_e / rem_n 是 Yen 算法在求 spur 路径时
// 用来"屏蔽某些边/节点"的临时禁用集合；首次调用传空集即标准 Dijkstra。
//
// 算法步骤：
//   1) dist[src]=0 入堆；其他节点的 dist 看 unordered_map::find 为 +∞
//   2) 反复出堆当前 dist 最小的节点 u；若 u==dst 直接回溯输出
//   3) 对 u 的每条 outgoing edge 做 relax：nd = w.t + e.time，
//      比 dist[v] 旧值小就更新 + 入堆
//
// "done" 集合保证每个节点最多展开一次（懒删除策略下的 Dijkstra 标准做法）。
std::vector<std::string> dijk_time(const std::string& src, const std::string& dst,
                                    const Graph& g, const StationManager& m,
                                    const std::unordered_set<std::string>& rem_e,
                                    const std::unordered_set<std::string>& rem_n) {
    std::unordered_map<std::string, int> dist{{src, 0}};
    std::unordered_map<std::string, Pred> cf{{src, {}}};
    std::priority_queue<std::pair<TimeW, std::string>,
                        std::vector<std::pair<TimeW, std::string>>,
                        std::greater<>> pq;
    pq.push({TimeW{0}, src});
    std::unordered_set<std::string> done;

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();
        if (done.count(u) || rem_n.count(u)) continue;
        done.insert(u);
        if (u == dst) return walk_back(dst, cf);

        for (const auto& e : g.neighbors(u)) {
            if (!target_open(m, e)) continue;          // 关闭站点跳过
            const auto& v = e.to_id;
            if (rem_n.count(v) || rem_e.count(ekey(u, v))) continue;  // Yen 屏蔽
            int nd = w.t + e.time;
            auto it = dist.find(v);
            if (it == dist.end() || nd < it->second) {
                dist[v] = nd;
                cf[v] = {u, e.line, e.direction, e.time, e.is_transfer()};
                pq.push({TimeW{nd}, v});
            }
        }
    }
    return {};
}

// ============================================================================
// dijk_xfr —— 最少换乘 Dijkstra（M4）
// ============================================================================
// 与 dijk_time 几乎同构，但权值是二维 XfrW{transfers, time}，字典序比较。
// 多维护一个 node_line[u] = "到 u 时所骑乘的线路名"，用来判断"换乘"事件：
//
//   • 走换乘边时不增加换乘计数（站台间步行），node_line 透传不变
//   • 走乘车边时若 line 与当前线路不同 → 计为一次新换乘
//
// 注意：node_line[src] 初始化为 ""——空串语义是"尚未骑乘任何线路"。
// 若起点是换乘站 (用户挑了 0213/2号线) 且最优路径立即换到 0113/1号线，
// 那段换乘 walk 不算"骑乘 2 号线"，符合乘客视角（见 assemble 节注释）。
std::vector<std::string> dijk_xfr(const std::string& src, const std::string& dst,
                                   const Graph& g, const StationManager& m,
                                   const std::unordered_set<std::string>& rem_e,
                                   const std::unordered_set<std::string>& rem_n) {
    std::unordered_map<std::string, XfrW> dist{{src, {0, 0}}};
    std::unordered_map<std::string, Pred> cf{{src, {}}};
    std::unordered_map<std::string, std::string> node_line{{src, ""}};
    std::priority_queue<std::pair<XfrW, std::string>,
                        std::vector<std::pair<XfrW, std::string>>,
                        std::greater<>> pq;
    pq.push({{0, 0}, src});
    std::unordered_set<std::string> done;

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();
        if (done.count(u) || rem_n.count(u)) continue;
        done.insert(u);
        if (u == dst) return walk_back(dst, cf);

        const auto& cl = node_line[u];   // "到 u 时所骑乘的线路"
        for (const auto& e : g.neighbors(u)) {
            if (!target_open(m, e)) continue;
            const auto& v = e.to_id;
            if (rem_n.count(v) || rem_e.count(ekey(u, v))) continue;
            int nt = w.t + e.time;
            // 是否构成一次新换乘：(a) 走的是乘车边 (b) 已经骑过线 (c) 与新边线路不同
            int nx = w.x + (!e.is_transfer() && !cl.empty() && e.line != cl ? 1 : 0);
            XfrW nw{nx, nt};
            // 决定到 v 之后"所骑乘的线路"：换乘边透传旧线，乘车边切到边自带的线
            std::string vl = e.is_transfer() ? cl : e.line;
            auto it = dist.find(v);
            if (it == dist.end() || nw < it->second) {
                if (!vl.empty()) node_line[v] = vl;
                dist[v] = nw;
                cf[v] = {u, e.line, e.direction, e.time, e.is_transfer()};
                pq.push({nw, v});
            }
        }
    }
    return {};
}

// ----------------------------------------------------------------------------
// Yen 算法用的"候选路径排序键"：与上面两个 Dijkstra 对应
// ----------------------------------------------------------------------------
// 通过把一条已知 ID 序列扫一遍累计权值，给 Yen 候选堆当 priority key。
// 注意：这里是事后计算，不是 Dijkstra 内部 dist；结果可能与 Dijkstra 内部
// 的 dist 略有差异（如 dijk_xfr 起点为换乘站的边缘情况），但用作 Yen 候选
// 的相对排序足够。

long long key_time(const std::vector<std::string>& ids, const Graph& g) {
    long long t = 0;
    for (size_t i = 1; i < ids.size(); ++i) {
        const Edge* e = g.get_edge(ids[i - 1], ids[i]);
        if (e) t += e->time;
    }
    return t;
}

long long key_xfr(const std::vector<std::string>& ids, const Graph& g) {
    // 把 (换乘数, 时间) 压成一个 long long：换乘数 * 1e6 + 时间
    // 这样比较 long long 等价于先比换乘数再比时间，符合字典序。
    int x = 0, t = 0;
    std::string cur_line;
    for (size_t i = 1; i < ids.size(); ++i) {
        const Edge* e = g.get_edge(ids[i - 1], ids[i]);
        if (!e) continue;
        t += e->time;
        if (!e->is_transfer()) {
            if (!cur_line.empty() && cur_line != e->line) ++x;
            cur_line = e->line;
        }
    }
    return static_cast<long long>(x) * 1000000LL + t;
}

// ============================================================================
// yen_k —— Yen's K-Shortest Paths 通用模板
// ============================================================================
// 给定第一条最优路径，迭代地寻找次优、第三优……至多 k 条互不重复的路径。
//
// Yen 算法核心思想：
//   设已找到前 ki 条路径 A[0..ki-1]，要找第 ki+1 条：
//   对 A[ki-1] 的每个分叉点 i（"spur node"）：
//     root = A[ki-1] 的前 i+1 个节点
//     屏蔽掉所有已找到路径中"前 i+1 个节点相同"的那条 (i, i+1) 边
//     屏蔽掉 root 上除 spur 之外的所有节点（避免回头）
//     从 spur 跑一次 Dijkstra 到 dst，得到 spur_path
//     总路径 = root[:-1] + spur_path，入候选堆
//   弹出候选堆里 key 最小的那条加入 A，作为第 ki+1 条
//
// 两个模板参数：
//   Search:  (spur, rem_e, rem_n) -> ids   实际跑 Dijkstra
//   KeyFn:   (ids, g)             -> key   给候选堆排序
template <typename Search, typename KeyFn>
std::vector<PathResult> yen_k(const std::vector<std::string>& first,
                               const Graph& g, const StationManager& m,
                               int k, Search search, KeyFn keyof) {
    std::vector<PathResult> A{ assemble(first, g, m) };

    // 候选最小堆（pair.first 越小越靠前；用 greater 反转）
    using Cand = std::pair<long long, std::vector<std::string>>;
    auto cmp = [](const Cand& a, const Cand& b) { return a.first > b.first; };
    std::priority_queue<Cand, std::vector<Cand>, decltype(cmp)> cand(cmp);
    std::unordered_set<std::string> seen;
    // pk: 把节点 ID 序列拼成唯一字符串作为去重 key（4 位 LLNN + '>' 分隔）
    auto pk = [](const std::vector<std::string>& v) {
        std::string s;
        s.reserve(v.size() * 5);
        for (const auto& x : v) { s += x; s += '>'; }
        return s;
    };
    seen.insert(pk(first));

    for (int ki = 1; ki < k; ++ki) {
        const auto& prev = A[ki - 1].ids;
        for (size_t i = 0; i + 1 < prev.size(); ++i) {
            const std::string& spur = prev[i];
            std::vector<std::string> root(prev.begin(), prev.begin() + i + 1);
            // 屏蔽所有"和 root 前缀相同"的已知路径的 (i, i+1) 边，
            // 强制本次 spur 搜索在 spur 节点处分叉。
            std::unordered_set<std::string> rem_e;
            for (const auto& ap : A) {
                if (ap.ids.size() <= i + 1) continue;
                bool same = true;
                for (size_t j = 0; j <= i; ++j) {
                    if (ap.ids[j] != root[j]) { same = false; break; }
                }
                if (same) rem_e.insert(ekey(ap.ids[i], ap.ids[i + 1]));
            }
            // 屏蔽 root 上除 spur 之外的所有节点，避免 spur 路径回头穿越。
            std::unordered_set<std::string> rem_n;
            for (size_t j = 0; j + 1 < root.size(); ++j)
                if (root[j] != spur) rem_n.insert(root[j]);

            auto spur_ids = search(spur, rem_e, rem_n);
            if (spur_ids.empty()) continue;

            // 总路径 = root 去掉末尾（即 spur）+ spur_ids（其首即 spur）
            std::vector<std::string> total(root.begin(), root.end() - 1);
            total.insert(total.end(), spur_ids.begin(), spur_ids.end());
            std::string kk = pk(total);
            if (seen.count(kk)) continue;        // 去重
            seen.insert(kk);
            cand.push({ keyof(total, g), total });
        }
        if (cand.empty()) break;                  // 候选已枯竭
        auto top = cand.top(); cand.pop();
        A.push_back(assemble(top.second, g, m));
    }
    return A;
}

} // namespace

// ============================================================================
// 对外 API —— 四个路径规划入口 + 一个格式化函数
// ============================================================================

// M3-1: 最短时间，单条
PathResult shortest_time(const std::string& src, const std::string& dst,
                          const Graph& g, const StationManager& m) {
    auto guarded = guard(src, dst, m);
    if (!guarded.ids.empty() || !guarded.valid) return guarded;
    auto ids = dijk_time(src, dst, g, m, {}, {});
    if (ids.empty()) { PathResult r; r.valid = false; r.error = "未找到可达路径。"; return r; }
    return assemble(ids, g, m);
}

// M4-1: 最少换乘，单条
PathResult min_transfers(const std::string& src, const std::string& dst,
                          const Graph& g, const StationManager& m) {
    auto guarded = guard(src, dst, m);
    if (!guarded.ids.empty() || !guarded.valid) return guarded;
    auto ids = dijk_xfr(src, dst, g, m, {}, {});
    if (ids.empty()) { PathResult r; r.valid = false; r.error = "未找到可达路径。"; return r; }
    return assemble(ids, g, m);
}

// M3-2: 最短时间，前 K 条
std::vector<PathResult> k_shortest_time(const std::string& src,
                                         const std::string& dst,
                                         const Graph& g,
                                         const StationManager& m, int k) {
    auto guarded = guard(src, dst, m);
    if (!guarded.ids.empty() || !guarded.valid) return { guarded };
    auto first = dijk_time(src, dst, g, m, {}, {});
    if (first.empty()) {
        PathResult r; r.valid = false; r.error = "未找到可达路径。"; return { r };
    }
    return yen_k(first, g, m, k,
                 [&](const std::string& s,
                      const std::unordered_set<std::string>& re,
                      const std::unordered_set<std::string>& rn) {
                     return dijk_time(s, dst, g, m, re, rn);
                 },
                 &key_time);
}

// M4-2: 最少换乘，前 K 条
std::vector<PathResult> k_min_transfers(const std::string& src,
                                         const std::string& dst,
                                         const Graph& g,
                                         const StationManager& m, int k) {
    auto guarded = guard(src, dst, m);
    if (!guarded.ids.empty() || !guarded.valid) return { guarded };
    auto first = dijk_xfr(src, dst, g, m, {}, {});
    if (first.empty()) {
        PathResult r; r.valid = false; r.error = "未找到可达路径。"; return { r };
    }
    return yen_k(first, g, m, k,
                 [&](const std::string& s,
                      const std::unordered_set<std::string>& re,
                      const std::unordered_set<std::string>& rn) {
                     return dijk_xfr(s, dst, g, m, re, rn);
                 },
                 &key_xfr);
}

// ============================================================================
// format —— 把 PathResult 渲染成多行控制台字符串
// ============================================================================
// 输出三部分：路径序列 + 汇总行 + 换乘点列表。
//   路径序列示例：
//     莘庄(1号线) -> 上海体育馆(1号线) --[换乘]-- 上海体育馆(4号线) -> ...
//   汇总行示例：
//     途经 11 站 | 总耗时: 33 分钟 | 换乘: 1 次
//   换乘点：
//     · 上海体育馆 (1号线 -> 4号线)
//
// 渲染逻辑两个细节：
//   ① 连续换乘边折叠：经过三线换乘站（如龙阳路 2/16/18 号线）会产生两条
//      连续换乘边，避免出现"--[换乘]-- --[换乘]--"中间没站名；
//   ② 换乘 marker 后不重复输出 " -> " 箭头：marker 本身已表达过渡关系。
std::string format(const PathResult& r, const StationManager& m, const Graph& g) {
    if (!r.valid) return std::string("[错误] ") + r.error;
    std::ostringstream out;

    if (r.ids.size() == 1) {
        const Station* s = m.get(r.ids[0]);
        out << (s ? s->name : r.ids[0]) << "（起终点相同）\n"
            << "总耗时: 0 分钟 | 换乘: 0 次";
        return out.str();
    }

    int physical = 0;                   // 已渲染出多少个物理站点
    bool prev_emitted_xfer = false;     // 上一个输出是否为换乘 marker
    for (size_t i = 0; i < r.ids.size(); ++i) {
        const Station* s = m.get(r.ids[i]);
        bool incoming_xfer = false;
        if (i > 0) {
            const Edge* e = g.get_edge(r.ids[i - 1], r.ids[i]);
            if (e && e->is_transfer()) incoming_xfer = true;
        }
        if (incoming_xfer) {
            if (!prev_emitted_xfer) {
                out << " --[换乘]-- ";
                prev_emitted_xfer = true;
            }
            // 中间换乘节点跳过站名（同一物理站的另一侧站台，会在下一条
            // 乘车边里以新线路名出现）；末节点保留站名让用户看到落地哪一侧。
            if (i + 1 != r.ids.size()) continue;
        }

        if (physical > 0 && !prev_emitted_xfer) out << " -> ";
        // 容错：ID 在图里但 manager 找不到对应 Station（数据不一致），
        // 用 [?id?] 显式占位，比静默吞掉一段路径更便于排查。
        std::string name = s ? s->name : ("[?" + r.ids[i] + "?]");
        std::string tag;
        if (s) {
            tag = "(" + s->line;
            auto it = r.line4_dirs.find(s->id);
            if (it != r.line4_dirs.end()) tag += it->second;  // 4 号线内/外圈
            tag += ")";
        }
        out << name << tag;
        ++physical;
        prev_emitted_xfer = false;
    }
    out << "\n\n途经 " << physical << " 站 | 总耗时: " << r.total_time
        << " 分钟 | 换乘: " << r.transfers << " 次";
    if (!r.transfer_at.empty()) {
        out << "\n换乘点:";
        for (const auto& [nm, fl, tl] : r.transfer_at) {
            out << "\n  · " << nm << " (" << fl << " -> " << tl << ")";
        }
    }
    return out.str();
}

// ============================================================================
// 网络分析（受关闭波及范围 + 全网连通分量数）
// ============================================================================

// 从 src_id 做 K 阶 BFS，返回波及到的所有 *开放* 站点 ID。
// 只走非换乘边——"影响范围"按地理拓扑算，换乘通道不能跨线扩散。
std::vector<std::string> affected_area(const std::string& src_id,
                                        const Graph& g,
                                        const StationManager& m,
                                        int order) {
    std::vector<std::string> out;
    if (!m.get(src_id) || order <= 0) return out;
    std::unordered_map<std::string, int> depth{{src_id, 0}};
    std::queue<std::string> q;
    q.push(src_id);
    while (!q.empty()) {
        auto u = q.front(); q.pop();
        int d = depth[u];
        if (d >= order) continue;
        // Use raw adjacency: walk physical edges (not transfer edges), so the
        // "affected by closure" radius is in the geographic sense.
        auto it = g.adj().find(u);
        if (it == g.adj().end()) continue;
        for (const auto& e : it->second) {
            if (e.is_transfer()) continue;          // 仅地理邻接，不跨线扩散
            const Station* s = m.get(e.to_id);
            if (!s || !s->open()) continue;         // 关闭站点同样被波及但不再扩散
            if (!depth.count(e.to_id)) {
                depth[e.to_id] = d + 1;
                out.push_back(e.to_id);
                q.push(e.to_id);
            }
        }
    }
    return out;
}

// 当前开放子图的连通分量数（迭代式 DFS）。
// 把有向图视作无向（按出边走就够了：原图把每段双向都建了两条有向边）。
// 关闭站点既不作为起点也不进入分量计数。
int component_count(const Graph& g, const StationManager& m) {
    std::unordered_set<std::string> visited;
    int comps = 0;
    for (const auto& [id, s] : m.all()) {
        if (!s.open() || visited.count(id)) continue;
        ++comps;
        std::vector<std::string> stack{id};
        visited.insert(id);
        while (!stack.empty()) {
            std::string u = stack.back(); stack.pop_back();
            auto it = g.adj().find(u);
            if (it == g.adj().end()) continue;
            for (const auto& e : it->second) {
                const Station* t = m.get(e.to_id);
                if (!t || !t->open() || visited.count(e.to_id)) continue;
                visited.insert(e.to_id);
                stack.push_back(e.to_id);
            }
        }
    }
    return comps;
}

} // namespace mini::pf
