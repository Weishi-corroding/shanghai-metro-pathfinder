// station.hpp —— 站点实体与站点管理器
//
// 数据模型：
//   • 物理上一座换乘车站（如人民广场覆盖 1/2/8 号线）在系统中拆分为多个
//     Station 节点，每条线路一个，各自拥有独立的 LLNN 站点 ID。
//   • LLNN = 2 位线路号 + 2 位线内序号，例如 0101 = 1 号线 1 号站（莘庄）。
//   • 各换乘节点之间通过 Graph 中的 "换乘" 边相连（5 分钟权重）。
//
// StationManager 责任：
//   • 加载 / 保存 Station.csv（UTF-8 BOM 编码）
//   • 维护 by_name_、by_line_ 两个倒排索引以支持模糊检索 / 线路列出
//   • 支持单站状态切换、批量 CSV 更新、初始状态恢复
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <filesystem>

namespace mini {

// 单个站点节点（已按线路拆分）
struct Station {
    std::string id;      // LLNN 格式，例如 "0101"
    std::string name;    // 中文站名（UTF-8）
    std::string line;    // 所属线路，例如 "1号线"、"浦江线"
    std::string status;  // 运营状态："开启" 或 "关闭"
    bool open() const { return status == "开启"; }
};

class StationManager {
public:
    // --- CSV 读写 ---
    void load(const std::filesystem::path& csv);
    void save(const std::filesystem::path& csv) const;

    // --- 查询接口（找不到时返回 nullptr / 空 vector）---
    const Station* get(const std::string& id) const;
    // 模糊检索：先尝试整名匹配（返回该名所有线路变体），失败再做子串扫描
    std::vector<const Station*> find_fuzzy(const std::string& kw) const;
    // 按线路列出该线全部站点（按 ID 升序，即线内运营顺序）
    std::vector<const Station*> of_line(const std::string& line) const;
    // 当前所有关闭状态的站点
    std::vector<const Station*> closed() const;
    // 同一物理站点关联的"其他线路"列表（用于"换乘：3号线 9号线"标注）
    std::vector<std::string> transfers_for(const std::string& name,
                                           const std::string& exclude_line) const;

    // --- 状态修改 ---
    bool set_status(const std::string& id, const std::string& status);

    // --- 批量更新 -----------------------------------------------------------
    // 输入文件格式（首行表头）：站点名称, 所属线路, 运营状态
    // 按 (站名 + 线路) 双主键匹配 stations_；非法状态行/未匹配行被记录但不致命。
    struct BatchStats {
        int updated = 0;             // 实际被修改的站点数（按站点而非行）
        int not_found = 0;           // 未能匹配到任何站点的输入行数
        int invalid = 0;             // 字段不足或状态值非法的行数
        std::vector<std::string> errors;  // 逐行诊断信息（含行号 + 原因）
    };
    BatchStats batch_update(const std::filesystem::path& csv);

    // 用 Station_init.csv 恢复到初始状态；备份文件缺失时返回 false。
    bool restore_initial(const std::filesystem::path& init_csv);

    size_t size() const { return stations_.size(); }
    const std::unordered_map<std::string, Station>& all() const { return stations_; }

private:
    std::unordered_map<std::string, Station> stations_;            // id -> Station
    std::unordered_map<std::string, std::vector<std::string>> by_name_;
    std::unordered_map<std::string, std::vector<std::string>> by_line_;
    void rebuild_indexes();
};

} // namespace mini
