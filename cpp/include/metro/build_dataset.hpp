#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <unordered_map>
#include <filesystem>

namespace metro::build {

// Line number → Chinese name
extern const std::unordered_map<int, std::string> LINE_NAMES;

// All 20 metro lines
extern const std::vector<int> ALL_LINES;

// Transfer edge time cost (minutes)
constexpr int TRANSFER_TIME = 5;

// Convert line number to Chinese name string
std::string line_str(int line_num);

// Clean station name (strip whitespace)
std::string clean_name(const std::string& name);

// ---------------------------------------------------------------------------
// Main pipeline entry point
// ---------------------------------------------------------------------------
// Reads raw CSV files from raw_dir, writes canonical CSVs to out_dir.
// Returns true on success.
bool build_all(const std::filesystem::path& raw_dir,
               const std::filesystem::path& out_dir);

} // namespace metro::build
