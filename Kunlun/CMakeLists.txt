# Specify the minimum version for CMake
CMAKE_MINIMUM_REQUIRED(VERSION 3.2)

# Project's name 
PROJECT(Kunlun)

IF(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    SET(OPENSSL_LIBRARIES /usr/local/openssl/lib64/libcrypto.a /usr/local/openssl/lib64/libssl.a)
    SET(OPENSSL_INCLUDE_DIR /usr/local/openssl/include)
    SET(OPENSSL_DIR /usr/local/openssl/lib64)
ELSEIF(CMAKE_SYSTEM_NAME STREQUAL "Darwin")
    SET(OPENSSL_LIBRARIES /usr/local/lib/libcrypto.a /usr/local/lib/libssl.a)
    SET(OPENSSL_INCLUDE_DIR /usr/local/include)
    SET(OPENSSL_DIR /usr/local/lib)
ENDIF()

FIND_PACKAGE(OpenMP REQUIRED)

# FIND_PACKAGE(absl REQUIRED)


SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17 -fpic -Wno-deprecated-declarations -Wno-unused-result -Xpreprocessor -O3")

SET(CMAKE_CXX_LINK_EXECUTABLE "${CMAKE_CXX_LINK_EXECUTABLE} -ldl")

INCLUDE_DIRECTORIES(
    ${OPENSSL_INCLUDE_DIR}
    "/usr/local/include"
)

LINK_DIRECTORIES(
    /usr/local/lib
)

SET(EXECUTABLE_OUTPUT_PATH ${PROJECT_SOURCE_DIR}/build) 

include(CMakePrintHelpers)

foreach(key
  IN ITEMS
    NUMBER_OF_LOGICAL_CORES
    NUMBER_OF_PHYSICAL_CORES
    IS_64BIT
    HAS_SSE2
    OS_NAME
    OS_RELEASE
  )
  # query the item ${key} and save its value in the variable _${key}
  cmake_host_system_information(RESULT _${key} QUERY ${key})
  cmake_print_variables(_${key})
endforeach()

# let the preprocessor know about the system name
if(CMAKE_SYSTEM_NAME  STREQUAL "Linux")
  SET(IS_LINUX 1)
endif()
if(CMAKE_SYSTEM_NAME  STREQUAL "Darwin")
  SET(IS_MACOS 1)
endif()
if(CMAKE_SYSTEM_NAME  STREQUAL "Windows")
  SET(IS_WINDOWS 1)
endif()

configure_file(${PROJECT_SOURCE_DIR}/config/config.h.in ${PROJECT_SOURCE_DIR}/config/config.h @ONLY)

# TARGET_LINK_LIBRARIES(absl::flat_hash_map)

# vole
ADD_EXECUTABLE(test_vole test/test_vole.cpp)
TARGET_LINK_LIBRARIES(test_vole ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# okvs
ADD_EXECUTABLE(test_okvs test/test_okvs.cpp)
TARGET_LINK_LIBRARIES(test_okvs ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# netio
ADD_EXECUTABLE(test_netio test/test_netio.cpp)
TARGET_LINK_LIBRARIES(test_netio ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# ot
ADD_EXECUTABLE(test_naor_pinkas_ot test/test_naor_pinkas_ot.cpp)
TARGET_LINK_LIBRARIES(test_naor_pinkas_ot ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_iknp_ote test/test_iknp_ote.cpp)
TARGET_LINK_LIBRARIES(test_iknp_ote ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_alsz_ote test/test_alsz_ote.cpp)
TARGET_LINK_LIBRARIES(test_alsz_ote ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# ske  
ADD_EXECUTABLE(test_aes test/test_aes.cpp)
TARGET_LINK_LIBRARIES(test_aes ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# psi
ADD_EXECUTABLE(test_cwprf_psi test/test_cwprf_psi.cpp)
TARGET_LINK_LIBRARIES(test_cwprf_psi ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# pso
ADD_EXECUTABLE(test_cwprf_mqrpmt test/test_cwprf_mqrpmt.cpp)
TARGET_LINK_LIBRARIES(test_cwprf_mqrpmt ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_mqrpmt_psi test/test_mqrpmt_psi.cpp)
TARGET_LINK_LIBRARIES(test_mqrpmt_psi ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_mqrpmt_psi_card test/test_mqrpmt_psi_card.cpp)
TARGET_LINK_LIBRARIES(test_mqrpmt_psi_card ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_mqrpmt_psi_card_sum test/test_mqrpmt_psi_card_sum.cpp)
TARGET_LINK_LIBRARIES(test_mqrpmt_psi_card_sum ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_mqrpmt_psu test/test_mqrpmt_psu.cpp)
TARGET_LINK_LIBRARIES(test_mqrpmt_psu ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_mqrpmt_private_id test/test_mqrpmt_private_id.cpp)
TARGET_LINK_LIBRARIES(test_mqrpmt_private_id ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# oprf
ADD_EXECUTABLE(test_ddh_oprf test/test_ddh_oprf.cpp)
TARGET_LINK_LIBRARIES(test_ddh_oprf ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_ote_oprf test/test_ote_oprf.cpp)
TARGET_LINK_LIBRARIES(test_ote_oprf ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

ADD_EXECUTABLE(test_vole_oprf test/test_vole_oprf.cpp)
TARGET_LINK_LIBRARIES(test_vole_oprf ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# peqt
ADD_EXECUTABLE(test_peqt test/test_peqt.cpp)
TARGET_LINK_LIBRARIES(test_peqt ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)

# misc
ADD_EXECUTABLE(test_misc test/test_misc.cpp)
TARGET_LINK_LIBRARIES(test_misc ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX)




ADD_EXECUTABLE(my_mqrpmt_psi test/my_mqrpmt_psi.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psi ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

# PSI
ADD_EXECUTABLE(my_mqrpmt_psi_receiver test/my_mqrpmt_psi_receiver.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psi_receiver ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

ADD_EXECUTABLE(my_mqrpmt_psi_sender test/my_mqrpmt_psi_sender.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psi_sender ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

# PSI-Card
ADD_EXECUTABLE(my_mqrpmt_psi_card_receiver test/my_mqrpmt_psi_card_receiver.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psi_card_receiver ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

ADD_EXECUTABLE(my_mqrpmt_psi_card_sender test/my_mqrpmt_psi_card_sender.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psi_card_sender ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

# PSU (Private Set Union)
ADD_EXECUTABLE(my_mqrpmt_psu_receiver test/my_mqrpmt_psu_receiver.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psu_receiver ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

ADD_EXECUTABLE(my_mqrpmt_psu_sender test/my_mqrpmt_psu_sender.cpp)
TARGET_LINK_LIBRARIES(my_mqrpmt_psu_sender ${OPENSSL_LIBRARIES} OpenMP::OpenMP_CXX dl pthread)

# mcl
# add_executable(test_mcl test/test_mcl.cpp)
# target_link_libraries(test_mcl libmcl.a libgmp.a)


