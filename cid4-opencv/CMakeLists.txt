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

find_package(nlohmann_json CONFIG REQUIRED)

add_library(cid4_scene_loader src/cid4_scene.cpp)
target_include_directories(cid4_scene_loader PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_scene_loader PUBLIC nlohmann_json::nlohmann_json)

add_library(cid4_opencv_support src/cid4_opencv.cpp)
target_include_directories(cid4_opencv_support PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_opencv_support PUBLIC cid4_scene_loader nlohmann_json::nlohmann_json)

find_package(OpenCV QUIET CONFIG COMPONENTS core imgcodecs imgproc)

add_executable(main src/main.cpp)
set_target_properties(main PROPERTIES OUTPUT_NAME main)
target_compile_definitions(main PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
target_link_libraries(main PRIVATE cid4_opencv_support)

if(OpenCV_FOUND)
	target_compile_definitions(main PRIVATE PUBCHEM_OPENCV_RUNTIME_AVAILABLE=1)
	target_include_directories(main PRIVATE ${OpenCV_INCLUDE_DIRS})
	target_link_libraries(main PRIVATE ${OpenCV_LIBS})
	message(STATUS "OpenCV detected. Building main with image-processing workflows enabled.")
else()
	target_compile_definitions(main PRIVATE PUBCHEM_OPENCV_RUNTIME_AVAILABLE=0)
	message(STATUS "OpenCV not detected. Building main stub mode for compile-only development.")
endif()

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/opencv_support_test.cpp)
target_link_libraries(tests PRIVATE cid4_opencv_support GTest::gtest GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(tests DISCOVERY_TIMEOUT 30)
