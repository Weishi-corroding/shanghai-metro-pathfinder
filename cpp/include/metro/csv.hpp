#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <filesystem>
#include <fstream>

namespace metro::csv {

// ---------------------------------------------------------------------------
// Reader — lightweight CSV parser with UTF-8 BOM support
// ---------------------------------------------------------------------------
class Reader {
public:
    explicit Reader(const std::filesystem::path& path);

    // Read the header row; returns column names in order.
    std::vector<std::string> header() const { return header_; }

    // Read all rows as a vector of column-name→value maps.
    std::vector<std::unordered_map<std::string, std::string>> read_all();

private:
    std::filesystem::path path_;
    std::vector<std::string> header_;
    bool bom_skipped_ = false;

    void skip_bom(std::ifstream& file);
    std::vector<std::string> split_line(const std::string& line);
};

// ---------------------------------------------------------------------------
// Writer — lightweight CSV writer with optional UTF-8 BOM
// ---------------------------------------------------------------------------
class Writer {
public:
    // If write_bom is true, the UTF-8 BOM (\xEF\xBB\xBF) is written at the
    // start of the file (for Excel compatibility).
    explicit Writer(const std::filesystem::path& path, bool write_bom = true);

    void write_header(const std::vector<std::string>& columns);
    void write_row(const std::vector<std::string>& values);

private:
    std::ofstream file_;
    bool header_written_ = false;
};

} // namespace metro::csv
