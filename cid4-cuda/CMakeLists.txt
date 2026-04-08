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

add_library(cid4_scene_loader src/cid4_scene.cpp)
target_include_directories(cid4_scene_loader PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_scene_loader PUBLIC nlohmann_json::nlohmann_json)

add_library(cid4_cuda_buffers src/cid4_cuda_buffers.cpp)
target_include_directories(cid4_cuda_buffers PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_cuda_buffers PUBLIC cid4_scene_loader)

include(CheckLanguage)
check_language(CUDA)

set(PUBCHEM_CUDA_TOOLCHAIN_READY OFF)
if(CMAKE_CUDA_COMPILER)
	enable_language(CUDA)
	find_package(CUDAToolkit QUIET)
	if(CUDAToolkit_FOUND)
		set(PUBCHEM_CUDA_TOOLCHAIN_READY ON)
	endif()
endif()

add_executable(cuda_app src/cuda_app.cpp)
set_target_properties(cuda_app PROPERTIES OUTPUT_NAME cuda_app)
target_compile_definitions(cuda_app PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
target_link_libraries(cuda_app PRIVATE cid4_cuda_buffers)

if(PUBCHEM_CUDA_TOOLCHAIN_READY)
	add_library(cid4_cuda_runtime src/cid4_cuda_runtime.cu)
	target_include_directories(cid4_cuda_runtime PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
	set_target_properties(
		cid4_cuda_runtime
		PROPERTIES
			CUDA_STANDARD 17
			CUDA_STANDARD_REQUIRED ON
			CUDA_SEPARABLE_COMPILATION ON
	)
	target_link_libraries(cid4_cuda_runtime PUBLIC CUDAToolkit::cudart cid4_cuda_buffers)

	target_compile_definitions(cuda_app PRIVATE PUBCHEM_CUDA_RUNTIME_AVAILABLE=1)
	target_link_libraries(cuda_app PRIVATE cid4_cuda_runtime)
	message(STATUS "CUDA toolkit detected. Building cuda_app with CUDA distance-matrix execution enabled.")
else()
	target_compile_definitions(cuda_app PRIVATE PUBCHEM_CUDA_RUNTIME_AVAILABLE=0)
	message(STATUS "CUDA toolkit not detected. Building cuda_app stub mode for compile-only development.")
endif()

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/cuda_buffers_test.cpp)
target_link_libraries(
	tests
	PRIVATE cid4_cuda_buffers GTest::gtest GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(tests DISCOVERY_TIMEOUT 30)
