#include "metro/csv.hpp"

#include <sstream>
#include <stdexcept>
#include <cstring>

namespace metro::csv {

// ---------------------------------------------------------------------------
// Reader
// ---------------------------------------------------------------------------

Reader::Reader(const std::filesystem::path& path)
    : path_(path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + path.string());
    }

    skip_bom(file);

    // Read header line
    std::string header_line;
    if (!std::getline(file, header_line)) {
        throw std::runtime_error("Empty CSV file: " + path.string());
    }
    // Strip trailing \r (Windows line endings)
    if (!header_line.empty() && header_line.back() == '\r') {
        header_line.pop_back();
    }
    header_ = split_line(header_line);
}

void Reader::skip_bom(std::ifstream& file) {
    char buf[3];
    file.read(buf, 3);
    auto count = file.gcount();
    if (count == 3 && static_cast<unsigned char>(buf[0]) == 0xEF
        && static_cast<unsigned char>(buf[1]) == 0xBB
        && static_cast<unsigned char>(buf[2]) == 0xBF) {
        bom_skipped_ = true;
        return;
    }
    // No BOM — rewind to start
    file.seekg(0);
}

std::vector<std::string> Reader::split_line(const std::string& line) {
    std::vector<std::string> result;
    std::string field;
    bool in_quotes = false;

    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (in_quotes) {
            if (c == '"') {
                // Check for escaped quote ""
                if (i + 1 < line.size() && line[i + 1] == '"') {
                    field += '"';
                    ++i;  // skip next quote
                } else {
                    in_quotes = false;
                }
            } else {
                field += c;
            }
        } else {
            if (c == '"') {
                in_quotes = true;
            } else if (c == ',') {
                result.push_back(std::move(field));
                field.clear();
            } else {
                field += c;
            }
        }
    }
    result.push_back(std::move(field));
    return result;
}

std::vector<std::unordered_map<std::string, std::string>> Reader::read_all() {
    std::vector<std::unordered_map<std::string, std::string>> rows;

    std::ifstream file(path_, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + path_.string());
    }
    skip_bom(file);

    // Skip header
    std::string dummy;
    std::getline(file, dummy);

    // Read data rows
    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.empty()) continue;

        auto fields = split_line(line);
        std::unordered_map<std::string, std::string> row;
        for (size_t i = 0; i < header_.size() && i < fields.size(); ++i) {
            row[header_[i]] = fields[i];
        }
        rows.push_back(std::move(row));
    }

    return rows;
}

// ---------------------------------------------------------------------------
// Writer
// ---------------------------------------------------------------------------

Writer::Writer(const std::filesystem::path& path, bool write_bom)
    : file_(path, std::ios::binary)
{
    if (!file_.is_open()) {
        throw std::runtime_error("Cannot open file for writing: " + path.string());
    }
    if (write_bom) {
        file_.write("\xEF\xBB\xBF", 3);
    }
}

void Writer::write_header(const std::vector<std::string>& columns) {
    if (header_written_) return;
    header_written_ = true;
    write_row(columns);
}

static std::string escape_csv_field(const std::string& field) {
    // If the field contains comma, quote, or newline, wrap in quotes
    bool needs_quote = false;
    for (char c : field) {
        if (c == ',' || c == '"' || c == '\n' || c == '\r') {
            needs_quote = true;
            break;
        }
    }
    if (!needs_quote) return field;

    std::string result = "\"";
    for (char c : field) {
        if (c == '"') result += "\"\"";
        else result += c;
    }
    result += "\"";
    return result;
}

void Writer::write_row(const std::vector<std::string>& values) {
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) file_ << ',';
        file_ << escape_csv_field(values[i]);
    }
    file_ << "\r\n";
}

} // namespace metro::csv
