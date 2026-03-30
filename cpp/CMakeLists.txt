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

set(PUBCHEM_RDKIT_PREFIX "$ENV{PUBCHEM_RDKIT_PREFIX}" CACHE PATH "Path to a conda or micromamba environment that provides RDKit")
if(NOT PUBCHEM_RDKIT_PREFIX AND DEFINED ENV{CONDA_PREFIX})
	set(PUBCHEM_RDKIT_PREFIX "$ENV{CONDA_PREFIX}" CACHE PATH "Path to a conda or micromamba environment that provides RDKit" FORCE)
endif()

if(PUBCHEM_RDKIT_PREFIX)
	list(PREPEND CMAKE_PREFIX_PATH "${PUBCHEM_RDKIT_PREFIX}")
endif()

find_package(Armadillo CONFIG REQUIRED)
find_package(Boost REQUIRED COMPONENTS graph)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(RDKit CONFIG REQUIRED)

set(pubchem_rdkit_rpath)
if(PUBCHEM_RDKIT_PREFIX AND EXISTS "${PUBCHEM_RDKIT_PREFIX}/lib")
	list(APPEND pubchem_rdkit_rpath "${PUBCHEM_RDKIT_PREFIX}/lib")
endif()

add_library(analysis_core src/analysis.cpp)
target_include_directories(
	analysis_core
	PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src
	PRIVATE ${ARMADILLO_INCLUDE_DIRS}
)
target_link_libraries(
	analysis_core
	PUBLIC ${ARMADILLO_LIBRARIES} Boost::graph nlohmann_json::nlohmann_json
)

add_executable(app src/app.cpp)
set_target_properties(app PROPERTIES OUTPUT_NAME app)
target_compile_definitions(app PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
if(pubchem_rdkit_rpath)
	set_target_properties(app PROPERTIES BUILD_RPATH "${pubchem_rdkit_rpath}" INSTALL_RPATH "${pubchem_rdkit_rpath}")
endif()
target_link_libraries(app
	PRIVATE
		analysis_core
		RDKit::Descriptors
		RDKit::FileParsers
		RDKit::GraphMol
		RDKit::RDGeneral
)

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/analysis_test.cpp)
target_link_libraries(tests PRIVATE analysis_core GTest::gtest GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(tests DISCOVERY_TIMEOUT 30)
