// csv.hpp —— 极简 UTF-8 CSV 读写器（标准库实现，零外部依赖）
//
// 支持的特性：
//   • 透明跳过 / 输出 UTF-8 BOM（Excel 中文兼容）
//   • 处理双引号包裹的字段（用 "" 转义内部双引号）
//   • Windows CRLF 行尾
//
// 不支持的特性（按"最小可行"原则裁剪）：
//   • 跨行字段、Mac 旧式 CR 行尾、字段内分号 / 自定义分隔符
#pragma once

#include <string>
#include <vector>
#include <filesystem>

namespace mini {

// 读取整个 CSV，第 0 个 vector 是表头行。自动跳过文件开头的 UTF-8 BOM。
std::vector<std::vector<std::string>> read_csv(const std::filesystem::path& path);

// 把 rows 写成 UTF-8（带 BOM）CSV；末尾会 flush + 校验 stream 状态，
// 若磁盘满/权限被收回/介质故障，会抛 std::runtime_error。
void write_csv(const std::filesystem::path& path,
               const std::vector<std::vector<std::string>>& rows);

// 去除字符串首尾的 ASCII 空白（空格、tab、\r、\n）。
std::string trim(const std::string& s);

} // namespace mini
