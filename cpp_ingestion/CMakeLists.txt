cmake_minimum_required(VERSION 3.10)
project(hft_watchlist_ingestion)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra")

# Find ZeroMQ
find_package(PkgConfig REQUIRED)
pkg_check_modules(ZMQ REQUIRED libzmq)

# Include ZeroMQ C++ bindings
find_path(CPPZMQ_INCLUDE_DIR zmq.hpp REQUIRED)

# Add executable
add_executable(ingestion_engine main.cpp zmq_publisher.cpp tick_simulator.cpp)

# Link libraries
target_include_directories(ingestion_engine PRIVATE ${CPPZMQ_INCLUDE_DIR} ${ZMQ_INCLUDE_DIRS})
target_link_libraries(ingestion_engine PRIVATE ${ZMQ_LIBRARIES})

# Installation target (optional)
install(TARGETS ingestion_engine DESTINATION bin)
