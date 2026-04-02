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
set(CROW_ENABLE_SSL ON)

option(PUBCHEM_ENABLE_VULKAN_APP "Build the optional CID 4 Vulkan viewer bootstrap" ON)
option(PUBCHEM_ENABLE_OPENGL_APP "Build the optional CID 4 OpenGL viewer bootstrap" ON)
option(PUBCHEM_ENABLE_CUDA_APP "Build the optional CID 4 CUDA geometry analyzer" ON)
option(PUBCHEM_ENABLE_OPENCV_APP "Build the optional CID 4 OpenCV image diagnostics tool" ON)

set(PUBCHEM_RDKIT_PREFIX "$ENV{PUBCHEM_RDKIT_PREFIX}" CACHE PATH "Path to a conda or micromamba environment that provides RDKit")
if(NOT PUBCHEM_RDKIT_PREFIX AND DEFINED ENV{CONDA_PREFIX})
	set(PUBCHEM_RDKIT_PREFIX "$ENV{CONDA_PREFIX}" CACHE PATH "Path to a conda or micromamba environment that provides RDKit" FORCE)
endif()

if(PUBCHEM_RDKIT_PREFIX)
	list(PREPEND CMAKE_PREFIX_PATH "${PUBCHEM_RDKIT_PREFIX}")
endif()

if(APPLE AND EXISTS "/usr/local/opt/openssl@3")
	set(OPENSSL_ROOT_DIR "/usr/local/opt/openssl@3")
endif()

find_package(Armadillo CONFIG REQUIRED)
find_package(Boost REQUIRED COMPONENTS graph)
find_package(Crow CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(OpenSSL REQUIRED)
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
	PUBLIC ${ARMADILLO_LIBRARIES} Boost::graph nlohmann_json::nlohmann_json RDKit::GraphMol RDKit::RDGeneral
)

add_library(cid4_scene_loader src/cid4_scene.cpp)
target_include_directories(cid4_scene_loader PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_scene_loader PUBLIC nlohmann_json::nlohmann_json)

add_library(cid4_opencv_support src/cid4_opencv.cpp)
target_include_directories(cid4_opencv_support PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_opencv_support PUBLIC cid4_scene_loader nlohmann_json::nlohmann_json)

add_library(cid4_cuda_buffers src/cid4_cuda_buffers.cpp)
target_include_directories(cid4_cuda_buffers PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cid4_cuda_buffers PUBLIC cid4_scene_loader)

add_library(cid4_http_support src/cid4_http.cpp)
target_include_directories(cid4_http_support PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_compile_definitions(
	cid4_http_support
	PUBLIC PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data"
)
target_link_libraries(cid4_http_support PUBLIC nlohmann_json::nlohmann_json)

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

add_executable(crow_api_server src/crow_api_server.cpp)
set_target_properties(crow_api_server PROPERTIES OUTPUT_NAME crow_api_server)
target_compile_definitions(crow_api_server PRIVATE CROW_ENABLE_SSL)
target_link_libraries(crow_api_server PRIVATE cid4_http_support Crow::Crow OpenSSL::SSL OpenSSL::Crypto)

if(PUBCHEM_ENABLE_VULKAN_APP)
	find_package(Vulkan QUIET)

	add_executable(vulkan_app src/vulkan_app.cpp)
	set_target_properties(vulkan_app PROPERTIES OUTPUT_NAME vulkan_app)
	target_compile_definitions(vulkan_app PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
	target_link_libraries(vulkan_app PRIVATE cid4_scene_loader)

	if(Vulkan_FOUND)
		target_compile_definitions(vulkan_app PRIVATE PUBCHEM_VULKAN_RUNTIME_AVAILABLE=1)
		target_link_libraries(vulkan_app PRIVATE Vulkan::Vulkan)
		message(STATUS "Vulkan SDK detected. Building vulkan_app with Vulkan runtime probing enabled.")
	else()
		target_compile_definitions(vulkan_app PRIVATE PUBCHEM_VULKAN_RUNTIME_AVAILABLE=0)
		message(STATUS "Vulkan SDK not detected. Building vulkan_app stub mode for compile-only development.")
	endif()
endif()

if(PUBCHEM_ENABLE_OPENGL_APP)
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
endif()

if(PUBCHEM_ENABLE_CUDA_APP)
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
endif()

if(PUBCHEM_ENABLE_OPENCV_APP)
	find_package(OpenCV QUIET CONFIG COMPONENTS core imgcodecs imgproc)

	add_executable(opencv_app src/opencv_app.cpp)
	set_target_properties(opencv_app PROPERTIES OUTPUT_NAME opencv_app)
	target_compile_definitions(opencv_app PRIVATE PUBCHEM_DEFAULT_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../data")
	target_link_libraries(opencv_app PRIVATE cid4_opencv_support)

	if(OpenCV_FOUND)
		target_compile_definitions(opencv_app PRIVATE PUBCHEM_OPENCV_RUNTIME_AVAILABLE=1)
		target_include_directories(opencv_app PRIVATE ${OpenCV_INCLUDE_DIRS})
		target_link_libraries(opencv_app PRIVATE ${OpenCV_LIBS})
		message(STATUS "OpenCV detected. Building opencv_app with image-processing workflows enabled.")
	else()
		target_compile_definitions(opencv_app PRIVATE PUBCHEM_OPENCV_RUNTIME_AVAILABLE=0)
		message(STATUS "OpenCV not detected. Building opencv_app stub mode for compile-only development.")
	endif()
endif()

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/analysis_test.cpp test/cuda_buffers_test.cpp test/opencv_support_test.cpp)
target_sources(tests PRIVATE test/cid4_http_test.cpp)
target_link_libraries(
	tests
	PRIVATE analysis_core cid4_cuda_buffers cid4_opencv_support cid4_http_support GTest::gtest GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(tests DISCOVERY_TIMEOUT 30)
