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

project(pubchem_cid4_analysis VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(APPLE AND EXISTS "/usr/local/opt/openssl@3")
	set(OPENSSL_ROOT_DIR "/usr/local/opt/openssl@3")
endif()

find_package(Boost REQUIRED COMPONENTS system)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

add_library(cid4_http_support src/cid4_http.cpp)
target_include_directories(cid4_http_support PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_compile_definitions(
	cid4_http_support
	PUBLIC PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data"
)
target_link_libraries(cid4_http_support PUBLIC nlohmann_json::nlohmann_json)

add_executable(main src/main.cpp)
set_target_properties(main PROPERTIES OUTPUT_NAME main)
target_link_libraries(
	main
	PRIVATE cid4_http_support Boost::system OpenSSL::SSL OpenSSL::Crypto Threads::Threads
)
