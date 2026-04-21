#include "app_utils.hpp"

namespace app::utils {
namespace env {
std::optional<std::string> getEnvValue(const std::string_view name)
{
    if (const char* value = std::getenv(name.data()); value != nullptr && value[0] != '\0') {
        return std::string(value);
    }

    return std::nullopt;
}
} // namespace env

namespace net {
std::optional<std::uint16_t> parsePort(const std::optional<std::string>& value)
{
    if (!value.has_value()) {
        return std::nullopt;
    }

    const auto parsed = std::stoul(*value);
    if (parsed <= 0 || parsed > 65535) {
        throw std::out_of_range("Invalid server port");
    }
    return static_cast<std::uint16_t>(parsed);
}

std::uint16_t getServerPort()
{
    const auto value = app::utils::env::getEnvValue("SERVER_PORT");
    const auto port = parsePort(value);
    return port.has_value() ? port.value() : 8443;
}
} // namespace net
} // namespace app::utils
