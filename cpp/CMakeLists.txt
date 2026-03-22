cmake_minimum_required(VERSION 4.3.0)
project(pubchem_cid4_analysis VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_executable(app src/app.cpp)
set_target_properties(app PROPERTIES OUTPUT_NAME app)

find_package(Armadillo CONFIG REQUIRED)
target_include_directories(app PRIVATE ${ARMADILLO_INCLUDE_DIRS})
target_link_libraries(app PRIVATE ${ARMADILLO_LIBRARIES})

enable_testing()
find_package(GTest CONFIG REQUIRED)

add_executable(tests test/sample_test.cpp)
target_link_libraries(tests PRIVATE GTest::gtest GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(tests)
