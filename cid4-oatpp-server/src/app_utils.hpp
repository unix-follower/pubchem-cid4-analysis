#pragma once

#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>

namespace app::utils {
namespace env {
std::optional<std::string> getEnvValue(const std::string_view name);
}
namespace net {
std::uint16_t getServerPort();

std::optional<std::uint16_t> parsePort(const std::optional<std::string>& value);
} // namespace net
} // namespace app::utils
