cmake_minimum_required(VERSION 3.18)

project(ibnot_new_cli LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CGAL REQUIRED)
find_package(Eigen3 REQUIRED NO_MODULE)

add_executable(ibnot_new_cli
    matrix/sparse_array.cpp
    matrix/sparse_matrix.cpp
    assign.cpp
    energy.cpp
    histogram.cpp
    init.cpp
    io.cpp
    main_cli.cpp
    optimizer.cpp
    regularity.cpp
    sites.cpp
)

target_include_directories(ibnot_new_cli PRIVATE .)
target_link_libraries(ibnot_new_cli PRIVATE CGAL::CGAL Eigen3::Eigen)
