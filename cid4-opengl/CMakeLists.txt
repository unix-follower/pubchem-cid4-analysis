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

find_package(OpenGL REQUIRED)
find_package(glfw3 REQUIRED CONFIG)

add_executable(cid4_opengl src/cid4_opengl.cpp)
set_target_properties(cid4_opengl PROPERTIES OUTPUT_NAME cid4_opengl)
target_link_libraries(cid4_opengl PRIVATE cid4_scene_loader)

target_link_libraries(cid4_opengl PRIVATE OpenGL::GL glfw)
