// csv.cpp —— 实现见 csv.hpp 头文件说明。
#include "csv.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace mini {

std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r' || s[a] == '\n')) ++a;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t' ||
                     s[b - 1] == '\r' || s[b - 1] == '\n')) --b;
    return s.substr(a, b - a);
}

// 解析一条已剥离行尾 \r\n 的 CSV 行。
// 状态机：in_quote 标记当前是否在双引号字段内；
//   • 引号内的 "" 视作字面量 "
//   • 引号外的 , 视作字段分隔符
//   • 字段开头的 " 进入引号模式（仅当 cur 为空时识别为开引，避免 a"b 误判）
static std::vector<std::string> parse_line(const std::string& line) {
    std::vector<std::string> fields;
    std::string cur;
    bool in_quote = false;
    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (in_quote) {
            if (c == '"') {
                if (i + 1 < line.size() && line[i + 1] == '"') { cur += '"'; ++i; }
                else in_quote = false;
            } else cur += c;
        } else {
            if (c == ',') { fields.push_back(cur); cur.clear(); }
            else if (c == '"' && cur.empty()) in_quote = true;
            else cur += c;
        }
    }
    fields.push_back(cur);
    return fields;
}

std::vector<std::vector<std::string>> read_csv(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("无法打开文件: " + path.string());

    std::vector<std::vector<std::string>> out;
    std::string line;
    bool first = true;
    while (std::getline(in, line)) {
        if (first) {
            first = false;
            // 跳过文件首的 UTF-8 BOM（0xEF 0xBB 0xBF），常见于 Excel 导出
            if (line.size() >= 3 &&
                static_cast<unsigned char>(line[0]) == 0xEF &&
                static_cast<unsigned char>(line[1]) == 0xBB &&
                static_cast<unsigned char>(line[2]) == 0xBF) {
                line.erase(0, 3);
            }
        }
        // 剥掉 Windows CRLF 中的 \r（getline 已吃掉 \n）
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        out.push_back(parse_line(line));
    }
    return out;
}

// 若字段含 , " 或换行则用引号包裹并把内部 " 转义为 ""
static std::string quote_if_needed(const std::string& s) {
    bool need = false;
    for (char c : s) {
        if (c == ',' || c == '"' || c == '\n' || c == '\r') { need = true; break; }
    }
    if (!need) return s;
    std::string out = "\"";
    for (char c : s) {
        if (c == '"') out += "\"\"";
        else out += c;
    }
    out += '"';
    return out;
}

void write_csv(const std::filesystem::path& path,
               const std::vector<std::vector<std::string>>& rows) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("无法写入文件: " + path.string());
    // 写 UTF-8 BOM（Excel 在中文环境下需要 BOM 才能正确识别编码）
    out.put(static_cast<char>(0xEF));
    out.put(static_cast<char>(0xBB));
    out.put(static_cast<char>(0xBF));
    for (const auto& r : rows) {
        for (size_t i = 0; i < r.size(); ++i) {
            if (i) out << ',';
            out << quote_if_needed(r[i]);
        }
        out << "\r\n";
    }
    // 主动 flush + 检查流状态：若磁盘满 / 权限被收回 / 介质故障，failbit 会
    // 静默置位，必须显式查询才能发现。否则函数会假报"成功"。
    out.flush();
    if (!out) {
        throw std::runtime_error(
            "写入文件失败（磁盘已满/权限不足/介质错误）: " + path.string());
    }
}

} // namespace mini
