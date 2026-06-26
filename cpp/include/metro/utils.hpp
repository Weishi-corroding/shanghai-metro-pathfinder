#pragma once

#include <string>
#include <string_view>
#include <utility>

namespace metro {

class StationManager;

namespace utils {

// Read menu choice with validation [min_val, max_val]. Retries until valid.
int read_menu_choice(const std::string& prompt, int min_val, int max_val);

// Read any integer. Retries until valid.
int read_int(const std::string& prompt);

// Read Y/N confirmation. Returns true for yes.
bool read_yes_no(const std::string& prompt = "Are you sure? (Y/N): ");

// Fuzzy station selection — shows numbered candidate list, returns station_id
// or empty string if user aborts.
std::string fuzzy_select_station(const StationManager& mgr,
                                  const std::string& keyword = "",
                                  const std::string& prompt_text = "Enter station keyword: ");

// Read start and end station IDs via fuzzy matching.
// Returns pair<src_id, dst_id>; empty strings on failure.
std::pair<std::string, std::string>
read_start_end_station(const StationManager& mgr, const std::string& mode_name);

// Print a decorative section header.
void print_path_header(const std::string& title);

} // namespace utils
} // namespace metro
