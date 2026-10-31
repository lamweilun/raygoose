cmake_minimum_required(VERSION 3.27)
project(raygoose C CXX)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "raygoose supports 64-bit targets only: C pointers cross as u64")
endif()

# raylib is vendored as a submodule and built from its own CMake project, so its
# per-platform dependencies (winmm/gdi32/opengl32 on Windows, the Cocoa/IOKit/
# OpenGL frameworks on macOS, X11/GL on Linux) travel with the target's link
# closure and reach the Goose program.
set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(BUILD_GAMES OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
add_subdirectory(vendor/raylib raylib_build)

# The adapters the binding needs (variadics, padded structs, C `long`, raymath
# inline wrappers) plus the layout asserts that keep the generated structs
# honest against the real headers on every target.
add_library(raygoose_native STATIC src/shims.c src/layout_check.c)
target_include_directories(raygoose_native PRIVATE vendor/raylib/src)
target_link_libraries(raygoose_native PUBLIC raylib)
