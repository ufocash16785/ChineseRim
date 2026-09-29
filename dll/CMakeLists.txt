cmake_minimum_required(VERSION 3.21)
project(ChineseRim VERSION 0.1.0 LANGUAGES CXX)

# 依 CommonLibSSE-NG 範本：vcpkg 安裝 commonlibsse-ng
# cmake --preset vs2022-windows && cmake --build build --config Release
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(CommonLibSSE CONFIG REQUIRED)

add_commonlibsse_plugin(${PROJECT_NAME}
    AUTHOR "ChineseRim Team"
    SOURCES
        src/plugin.cpp
        src/Papyrus.cpp
        src/ElementHook.cpp
        src/Flight.cpp
        src/RealmKeyword.cpp
        src/DataRegistry.cpp
)

target_include_directories(${PROJECT_NAME} PRIVATE src)
target_precompile_headers(${PROJECT_NAME} PRIVATE src/PCH.h)

# 輸出到 MO2 可直接讀取的路徑
install(TARGETS ${PROJECT_NAME} DESTINATION "${CMAKE_SOURCE_DIR}/../SKSE/Plugins")
