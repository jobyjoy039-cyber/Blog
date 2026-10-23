cmake_minimum_required(VERSION 3.22.1)
project(videotranscriber LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# whisper.cpp build options: CPU only, static libs, no extras.
set(BUILD_SHARED_LIBS      OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS    OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER   OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE            OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP            OFF CACHE BOOL "" FORCE)

# Use a local checkout if one is given (-DWHISPER_CPP_DIR=...), otherwise
# fetch the pinned release with git at configure time.
set(WHISPER_CPP_DIR "" CACHE PATH "Path to a local whisper.cpp checkout")
if (WHISPER_CPP_DIR)
    add_subdirectory(${WHISPER_CPP_DIR} whisper.cpp EXCLUDE_FROM_ALL)
else()
    include(FetchContent)
    FetchContent_Declare(
        whisper
        GIT_REPOSITORY https://github.com/ggml-org/whisper.cpp.git
        GIT_TAG        v1.9.4
        GIT_SHALLOW    TRUE
    )
    FetchContent_GetProperties(whisper)
    if (NOT whisper_POPULATED)
        FetchContent_Populate(whisper)
        add_subdirectory(${whisper_SOURCE_DIR} ${whisper_BINARY_DIR} EXCLUDE_FROM_ALL)
    endif()
endif()

add_library(whisper_jni SHARED whisper_jni.cpp)
target_compile_options(whisper_jni PRIVATE -O3)
target_link_libraries(whisper_jni PRIVATE whisper android log)
