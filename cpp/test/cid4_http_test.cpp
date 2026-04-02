#include <gtest/gtest.h>

#include "cid4_http.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>

namespace {

class ScopedEnvironmentVariable {
  public:
    explicit ScopedEnvironmentVariable(std::string name) : name_(std::move(name))
    {
        const char* current = std::getenv(name_.c_str());
        if (current != nullptr) {
            originalValue_ = std::string(current);
        }
    }

    ~ScopedEnvironmentVariable()
    {
        if (originalValue_.has_value()) {
            setenv(name_.c_str(), originalValue_->c_str(), 1);
        }
        else {
            unsetenv(name_.c_str());
        }
    }

    void set(const std::string& value) const
    {
        setenv(name_.c_str(), value.c_str(), 1);
    }

    void unset() const
    {
        unsetenv(name_.c_str());
    }

  private:
    std::string name_;
    std::optional<std::string> originalValue_;
};

std::filesystem::path createTempDataDir()
{
    const auto uniqueSuffix =
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    const auto directory =
        std::filesystem::temp_directory_path() / "pubchem-cid4-http-tests" / uniqueSuffix;
    std::filesystem::create_directories(directory);
    std::ofstream(directory / "COMPOUND_CID_4.json") << "{}";
    std::ofstream(directory / "Structure2D_COMPOUND_CID_4.json") << R"({"PC_Compounds": []})";
    std::ofstream(directory / "Conformer3D_COMPOUND_CID_4(1).json") << R"({"PC_Compounds": []})";
    return directory;
}

} // namespace

TEST(Cid4HttpTest, ResolveDataDirPrefersExplicitDataDir)
{
    ScopedEnvironmentVariable dataDir("DATA_DIR");
    const auto directory = createTempDataDir();
    dataDir.set(directory.string());

    EXPECT_EQ(pubchem::cid4http::resolveDataDir(), directory);
}

TEST(Cid4HttpTest, ResolveServerConfigFallsBackToCryptoSummary)
{
    ScopedEnvironmentVariable cert("TLS_CERT_FILE");
    ScopedEnvironmentVariable key("TLS_KEY_FILE");
    ScopedEnvironmentVariable password("TLS_KEY_PASSWORD");
    ScopedEnvironmentVariable host("CROW_HOST");
    ScopedEnvironmentVariable port("CROW_PORT");

    cert.unset();
    key.unset();
    password.unset();
    host.set("127.0.0.1");
    port.set("9443");

    const auto directory = createTempDataDir();
    const auto certPath = directory / "cid4.demo.cert.pem";
    const auto keyPath = directory / "cid4.demo.key.pem";
    std::ofstream(certPath) << "demo-cert";
    std::ofstream(keyPath) << "demo-key";

    const auto summaryPath = directory / "out" / "crypto" / "cid4_crypto.summary.json";
    std::filesystem::create_directories(summaryPath.parent_path());
    std::ofstream(summaryPath) << "{\n"
                               << "  \"demo_password\": \"test-secret\",\n"
                               << "  \"x509_and_pkcs12\": {\n"
                               << "    \"pem_paths\": {\n"
                               << "      \"certificate\": \"" << certPath.string() << "\",\n"
                               << "      \"private_key\": \"" << keyPath.string() << "\"\n"
                               << "    }\n"
                               << "  }\n"
                               << "}";

    const auto config =
        pubchem::cid4http::resolveServerConfig(directory, {"CROW_HOST"}, {"CROW_PORT"});
    EXPECT_EQ(config.host, "127.0.0.1");
    EXPECT_EQ(config.port, 9443);
    ASSERT_TRUE(config.keyPassword.has_value());
    EXPECT_EQ(*config.keyPassword, "test-secret");
    EXPECT_EQ(config.certFile, certPath);
    EXPECT_EQ(config.keyFile, keyPath);
}

TEST(Cid4HttpTest, ResolveServerConfigUsesGenericServerFallbacks)
{
    ScopedEnvironmentVariable cert("TLS_CERT_FILE");
    ScopedEnvironmentVariable key("TLS_KEY_FILE");
    ScopedEnvironmentVariable password("TLS_KEY_PASSWORD");
    ScopedEnvironmentVariable host("SERVER_HOST");
    ScopedEnvironmentVariable port("SERVER_PORT");

    cert.unset();
    key.unset();
    password.unset();
    host.set("127.0.0.2");
    port.set("9555");

    const auto directory = createTempDataDir();
    const auto certPath = directory / "cid4.demo.cert.pem";
    const auto keyPath = directory / "cid4.demo.key.pem";
    std::ofstream(certPath) << "demo-cert";
    std::ofstream(keyPath) << "demo-key";

    const auto summaryPath = directory / "out" / "crypto" / "cid4_crypto.summary.json";
    std::filesystem::create_directories(summaryPath.parent_path());
    std::ofstream(summaryPath) << "{\n"
                               << "  \"x509_and_pkcs12\": {\n"
                               << "    \"pem_paths\": {\n"
                               << "      \"certificate\": \"" << certPath.string() << "\",\n"
                               << "      \"private_key\": \"" << keyPath.string() << "\"\n"
                               << "    }\n"
                               << "  }\n"
                               << "}";

    const auto config = pubchem::cid4http::resolveServerConfig(directory);
    EXPECT_EQ(config.host, "127.0.0.2");
    EXPECT_EQ(config.port, 9555);
}

TEST(Cid4HttpTest, SupportedConformerIndexIsBounded)
{
    EXPECT_FALSE(pubchem::cid4http::isSupportedConformerIndex(0));
    EXPECT_TRUE(pubchem::cid4http::isSupportedConformerIndex(1));
    EXPECT_TRUE(pubchem::cid4http::isSupportedConformerIndex(6));
    EXPECT_FALSE(pubchem::cid4http::isSupportedConformerIndex(7));
}

TEST(Cid4HttpTest, LoadJsonPayloadThrowsForMissingFile)
{
    EXPECT_THROW(pubchem::cid4http::loadJsonPayload(std::filesystem::path("missing.json")),
                 std::runtime_error);
}

TEST(Cid4HttpTest, FixturePayloadsExposeExpectedTopLevelFields)
{
    EXPECT_TRUE(pubchem::cid4http::pathwayFixture().contains("graph"));
    EXPECT_TRUE(pubchem::cid4http::bioactivityFixture().contains("records"));
    EXPECT_TRUE(pubchem::cid4http::taxonomyFixture().contains("organisms"));
}
