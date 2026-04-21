cmake_minimum_required(VERSION 4.3.0)

if(APPLE AND NOT CMAKE_OSX_SYSROOT)
	execute_process(
		COMMAND xcrun --sdk macosx --show-sdk-path
		OUTPUT_VARIABLE PUBCHEM_MACOS_SDK_PATH
		OUTPUT_STRIP_TRAILING_WHITESPACE
		ERROR_QUIET
	)

	if(PUBCHEM_MACOS_SDK_PATH)
		set(CMAKE_OSX_SYSROOT "${PUBCHEM_MACOS_SDK_PATH}" CACHE STRING "macOS SDK path" FORCE)
	endif()
endif()

project(cid4_oatpp VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(APPLE AND EXISTS "/usr/local/opt/openssl@3")
	set(OPENSSL_ROOT_DIR "/usr/local/opt/openssl@3")
endif()

find_package(nlohmann_json CONFIG REQUIRED)
find_package(oatpp CONFIG REQUIRED)
find_package(oatpp-openssl CONFIG REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(prometheus-cpp CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)

add_library(app_utils src/app_utils.cpp)
target_include_directories(app_utils PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

add_library(cid4_http_support src/cid4_http.cpp)
target_include_directories(cid4_http_support PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_http_support PUBLIC nlohmann_json::nlohmann_json)

add_library(observability src/observability.cpp)
target_include_directories(observability PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(
	observability
	PUBLIC
		nlohmann_json::nlohmann_json
		prometheus-cpp::pull
		spdlog::spdlog
		app_utils
)

add_executable(main src/main.cpp)
set_target_properties(main PROPERTIES OUTPUT_NAME main)
target_link_libraries(main PRIVATE cid4_http_support observability oatpp::oatpp oatpp::oatpp-openssl OpenSSL::SSL OpenSSL::Crypto)

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/main_test.cpp)
target_link_libraries(
	tests
	PRIVATE GTest::gtest GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(tests DISCOVERY_TIMEOUT 30)
