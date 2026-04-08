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

find_package(OpenGL QUIET)
find_package(glfw3 QUIET CONFIG)

add_executable(opengl_app src/opengl_app.cpp)
set_target_properties(opengl_app PROPERTIES OUTPUT_NAME opengl_app)
target_compile_definitions(opengl_app PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
target_link_libraries(opengl_app PRIVATE cid4_scene_loader)

if(OpenGL_FOUND AND glfw3_FOUND)
	target_compile_definitions(opengl_app PRIVATE PUBCHEM_OPENGL_RUNTIME_AVAILABLE=1)
	target_link_libraries(opengl_app PRIVATE OpenGL::GL glfw)
	message(STATUS "OpenGL and GLFW detected. Building opengl_app with runtime probing enabled.")
else()
	target_compile_definitions(opengl_app PRIVATE PUBCHEM_OPENGL_RUNTIME_AVAILABLE=0)
	message(STATUS "OpenGL and/or GLFW not detected. Building opengl_app stub mode for compile-only development.")
endif()
