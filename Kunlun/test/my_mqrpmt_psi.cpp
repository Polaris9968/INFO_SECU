// Kunlun 项目路径常量（项目根目录前缀）
#define KUNLUN_BASE_DIR "/root/projects/INFO_SECU_1.0/Kunlun"
#include "../mpc/pso/mqrpmt_psi.hpp"
#include "../crypto/setup.hpp"
#include <fstream>
#include <string>
#include <sstream>
#include <cmath>
#include <vector>
#include <set>
#include <algorithm>
#include <iomanip>
#include <cstring>
#include <iostream>
#include <unordered_map>
#include <openssl/sha.h>

// ============================================================================
// 0. 自定义 Block 比较器
// ============================================================================

struct BlockEqual {
    bool operator()(const block& a, const block& b) const {
        const uint64_t* pa = reinterpret_cast<const uint64_t*>(&a);
        const uint64_t* pb = reinterpret_cast<const uint64_t*>(&b);
        return pa[0] == pb[0] && pa[1] == pb[1];
    }
};

// 使用自定义的 BlockEqual
std::unordered_map<block, std::string, BlockHash, BlockEqual> block_to_string;

// ============================================================================
// 1. 数据结构
// ============================================================================

struct MyTestCase {
    std::vector<block> vec_X_original;
    std::vector<block> vec_Y_original;
    size_t SENDER_ITEM_NUM_ORIGINAL;
    size_t RECEIVER_ITEM_NUM_ORIGINAL;
    std::vector<block> vec_X_padded;
    std::vector<block> vec_Y_padded;
    size_t SENDER_ITEM_NUM_PADDED;
    size_t RECEIVER_ITEM_NUM_PADDED;
    std::vector<block> vec_intersection;
    size_t HAMMING_WEIGHT;
};

// ============================================================================
// 2. 辅助工具函数
// ============================================================================

size_t NextPowerOfTwo(size_t n) {
    if (n == 0) return 1;
    size_t power = 1;
    while (power < n) power <<= 1;
    return power;
}

// 将字符串转换为 block（支持十进制数字和十六进制字符串）
block MyStringToBlock(const std::string& input_str) {
    std::string clean = input_str;
    clean.erase(0, clean.find_first_not_of(" \t\n\r,"));
    clean.erase(clean.find_last_not_of(" \t\n\r,") + 1);
    
    if (clean.empty()) {
        return Block::MakeBlock(0LL, 0LL);
    }
    
    bool is_decimal = true;
    for (char c : clean) {
        if (!std::isdigit(c) && c != '-') {
            is_decimal = false;
            break;
        }
    }
    
    if (is_decimal) {
        try {
            unsigned long long num = std::stoull(clean);
            uint64_t high = 0;
            uint64_t low = num;
            std::ostringstream oss;
            oss << std::hex << std::setfill('0') 
                << std::setw(16) << high 
                << std::setw(16) << low;
            std::string hex_str = oss.str();
            
            std::vector<uint8_t> bytes(16, 0);
            for (size_t i = 0; i < 16; i++) {
                std::string byte_str = hex_str.substr(i*2, 2);
                bytes[i] = static_cast<uint8_t>(std::stoi(byte_str, nullptr, 16));
            }
            block result;
            memcpy(&result, bytes.data(), 16);
            return result;
        } catch (const std::exception& e) {
            // 转换失败，降级到哈希
        }
    }
    
    // 字符串：使用 SHA-256 哈希
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(clean.c_str()), clean.size(), hash);
    block result;
    memcpy(&result, hash, 16);
    return result;
}

// 修改 StringToBlock，同时记录映射（移到 MyStringToBlock 之后）
block MyStringToBlockWithMapping(const std::string& input_str) {
    block b = MyStringToBlock(input_str);
    block_to_string[b] = input_str;
    return b;
}

std::string BlockToString(const block& b) {
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(&b);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (int i = 0; i < 16; i++) {
        oss << std::setw(2) << static_cast<int>(bytes[i]);
    }
    return oss.str();
}

block GenerateDummyBlock(uint64_t seed) {
    block dummy;
    uint64_t* ptr = reinterpret_cast<uint64_t*>(&dummy);
    ptr[0] = seed;
    ptr[1] = seed ^ 0xFFFFFFFFFFFFFFFFULL;
    return dummy;
}

// ============================================================================
// 3. 从文件加载数据（空格分隔）
// ============================================================================

MyTestCase LoadTestCaseFromFiles() {
    MyTestCase testcase;
    const std::string sender_file = KUNLUN_BASE_DIR "/test/sender.txt";
    const std::string receiver_file = KUNLUN_BASE_DIR "/test/receiver.txt";
    
    std::ifstream fin_sender(sender_file);
    if (!fin_sender) {
        std::cerr << "Error: Cannot open " << sender_file << std::endl;
        exit(1);
    }
    
    std::string line;
    while (std::getline(fin_sender, line)) {
        if (line.empty() || line[0] == '#') continue;
        
        std::istringstream iss(line);
        std::string token;
        while (iss >> token) {
            token.erase(std::remove(token.begin(), token.end(), ','), token.end());
            if (token.empty()) continue;
            // 移除数字过滤，允许任何 token
            try {
                block b = MyStringToBlock(token);
                testcase.vec_X_original.push_back(b);
            } catch (const std::exception& e) {
                std::cerr << "Warning: Skipping invalid token: " << token << std::endl;
            }
        }
    }
    fin_sender.close();
    
    std::ifstream fin_receiver(receiver_file);
    if (!fin_receiver) {
        std::cerr << "Error: Cannot open " << receiver_file << std::endl;
        exit(1);
    }
    
    while (std::getline(fin_receiver, line)) {
        if (line.empty() || line[0] == '#') continue;
        
        std::istringstream iss(line);
        std::string token;
        while (iss >> token) {
            token.erase(std::remove(token.begin(), token.end(), ','), token.end());
            if (token.empty()) continue;
            // 移除数字过滤，允许任何 token
            try {
                block b = MyStringToBlockWithMapping(token);
                testcase.vec_Y_original.push_back(b);
            } catch (const std::exception& e) {
                std::cerr << "Warning: Skipping invalid token: " << token << std::endl;
            }
        }
    }
    fin_receiver.close();
    
    testcase.SENDER_ITEM_NUM_ORIGINAL = testcase.vec_X_original.size();
    testcase.RECEIVER_ITEM_NUM_ORIGINAL = testcase.vec_Y_original.size();
    
    std::cout << "[Load] Loaded " << testcase.SENDER_ITEM_NUM_ORIGINAL 
              << " sender items from " << sender_file << std::endl;
    std::cout << "[Load] Loaded " << testcase.RECEIVER_ITEM_NUM_ORIGINAL 
              << " receiver items from " << receiver_file << std::endl;
    
    return testcase;
}

// ============================================================================
// 4. 填充到 2 的幂次
// ============================================================================

void PadTestCase(MyTestCase& testcase, uint64_t dummy_seed = 0xDEADBEEF) {
    size_t min_size = 128;
    testcase.SENDER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.SENDER_ITEM_NUM_ORIGINAL), min_size);
    testcase.RECEIVER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.RECEIVER_ITEM_NUM_ORIGINAL), min_size);
    
    block dummy = GenerateDummyBlock(dummy_seed);
    
    testcase.vec_X_padded = testcase.vec_X_original;
    testcase.vec_Y_padded = testcase.vec_Y_original;
    
    size_t pad_sender = testcase.SENDER_ITEM_NUM_PADDED - testcase.SENDER_ITEM_NUM_ORIGINAL;
    testcase.vec_X_padded.resize(testcase.SENDER_ITEM_NUM_PADDED, dummy);
    
    size_t pad_receiver = testcase.RECEIVER_ITEM_NUM_PADDED - testcase.RECEIVER_ITEM_NUM_ORIGINAL;
    testcase.vec_Y_padded.resize(testcase.RECEIVER_ITEM_NUM_PADDED, dummy);
    
    std::cout << "[Pad] Sender: " << testcase.SENDER_ITEM_NUM_ORIGINAL 
              << " -> " << testcase.SENDER_ITEM_NUM_PADDED 
              << " (+" << pad_sender << ")" << std::endl;
    std::cout << "[Pad] Receiver: " << testcase.RECEIVER_ITEM_NUM_ORIGINAL 
              << " -> " << testcase.RECEIVER_ITEM_NUM_PADDED 
              << " (+" << pad_receiver << ")" << std::endl;
}

// ============================================================================
// 5. 截断结果
// ============================================================================

std::vector<block> TruncateResult(const std::vector<block>& result_padded, 
                                   size_t original_size) {
    if (result_padded.size() <= original_size) {
        return result_padded;
    }
    return std::vector<block>(result_padded.begin(), 
                              result_padded.begin() + original_size);
}

// ============================================================================
// 6. 保存结果到文件
// ============================================================================

void SaveResultToFile(const std::vector<block>& result, 
                      const std::string& filename) {
    block dummy = GenerateDummyBlock(0xDEADBEEF);
    const uint64_t* dummy_ptr = reinterpret_cast<const uint64_t*>(&dummy);
    uint64_t dummy_low = dummy_ptr[0];
    uint64_t dummy_high = dummy_ptr[1];
    
    std::stringstream ss;
    int saved_count = 0;
    
    for (size_t i = 0; i < result.size(); i++) {
        const uint64_t* ptr = reinterpret_cast<const uint64_t*>(&result[i]);
        uint64_t low = ptr[0];
        uint64_t high = ptr[1];
        
        if (low == dummy_low && high == dummy_high) {
            continue;
        }
        
        auto it = block_to_string.find(result[i]);
        if (it != block_to_string.end()) {
            ss << it->second << std::endl;
        } else {
            ss << std::hex << std::setw(16) << std::setfill('0') << high
               << std::setw(16) << std::setfill('0') << low << std::endl;
        }
        saved_count++;
    }
    
    std::ofstream fout(filename);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    fout << ss.str();
    fout.close();
    
    std::cout << "[Save] Saved " << saved_count << " items to " << filename << std::endl;
}

// ============================================================================
// 7. 打印测试用例信息
// ============================================================================

void PrintMyTestCase(const MyTestCase& testcase) {
    PrintSplitLine('-');
    std::cout << "TESTCASE INFO >>>" << std::endl;
    std::cout << "Sender original size: " << testcase.SENDER_ITEM_NUM_ORIGINAL << std::endl;
    std::cout << "Receiver original size: " << testcase.RECEIVER_ITEM_NUM_ORIGINAL << std::endl;
    std::cout << "Sender padded size: " << testcase.SENDER_ITEM_NUM_PADDED << std::endl;
    std::cout << "Receiver padded size: " << testcase.RECEIVER_ITEM_NUM_PADDED << std::endl;
    PrintSplitLine('-');
}

// ============================================================================
// 8. 主函数
// ============================================================================

int main() {
    CRYPTO_Initialize();
    
    std::cout << "========================================" << std::endl;
    std::cout << "    My mqRPMT-based PSI Test" << std::endl;
    std::cout << "    Reads sender.txt / receiver.txt" << std::endl;
    std::cout << "========================================" << std::endl;
    
    std::cout << "[Step 1] Loading data from files..." << std::endl;
    MyTestCase testcase = LoadTestCaseFromFiles();
    
    if (testcase.SENDER_ITEM_NUM_ORIGINAL == 0 || 
        testcase.RECEIVER_ITEM_NUM_ORIGINAL == 0) {
        std::cerr << "Error: Empty data files!" << std::endl;
        return 1;
    }
    
    std::cout << "[Step 2] Padding to power of two..." << std::endl;
    PadTestCase(testcase);
    PrintMyTestCase(testcase);
    
    std::cout << "[Step 3] Setting up public parameters..." << std::endl;
    size_t computational_security_parameter = 128;
    size_t statistical_security_parameter = 40;
    size_t LOG_SENDER = static_cast<size_t>(std::log2(testcase.SENDER_ITEM_NUM_PADDED));
    size_t LOG_RECEIVER = static_cast<size_t>(std::log2(testcase.RECEIVER_ITEM_NUM_PADDED));
    
    mqRPMTPSI::PP pp = mqRPMTPSI::Setup(
        computational_security_parameter,
        statistical_security_parameter,
        LOG_SENDER,
        LOG_RECEIVER
    );
    
    std::string party;
    std::cout << "[Step 4] Select role (sender/receiver): ";
    std::getline(std::cin, party);
    PrintSplitLine('-');
    
    if (party == "sender" || party == "Sender" || party == "SENDER") {
        std::cout << "[Sender] Starting..." << std::endl;
        NetIO client("client", "127.0.0.1", 8080);
        mqRPMTPSI::Send(client, pp, testcase.vec_X_padded);
        std::cout << "[Sender] Finished." << std::endl;
    }
    else if (party == "receiver" || party == "Receiver" || party == "RECEIVER") {
        std::cout << "[Receiver] Starting..." << std::endl;
        NetIO server("server", "", 8080);
        std::vector<block> result_padded = mqRPMTPSI::Receive(server, pp, testcase.vec_Y_padded);
        
        std::cout << "[Receiver] Truncating result..." << std::endl;
        size_t max_original_size = std::min(testcase.SENDER_ITEM_NUM_ORIGINAL, 
                                            testcase.RECEIVER_ITEM_NUM_ORIGINAL);
        std::vector<block> result = TruncateResult(result_padded, max_original_size);

        block dummy = GenerateDummyBlock(0xDEADBEEF);
        const uint64_t* dummy_ptr = reinterpret_cast<const uint64_t*>(&dummy);
        uint64_t dummy_low = dummy_ptr[0];
        uint64_t dummy_high = dummy_ptr[1];

        int actual_intersection_size = 0;
        for (const auto& block : result) {
            const uint64_t* ptr = reinterpret_cast<const uint64_t*>(&block);
            if (!(ptr[0] == dummy_low && ptr[1] == dummy_high)) {
                actual_intersection_size++;
            }
        }

        SaveResultToFile(result, "../test/intersection.txt");

        std::cout << "[Receiver] Actual intersection size (filtered): " << actual_intersection_size << std::endl;
        std::cout << "[Receiver] Finished." << std::endl;
    }
    else {
        std::cerr << "Error: Unknown role. Please enter 'sender' or 'receiver'." << std::endl;
    }
    
    std::cout << "========================================" << std::endl;
    CRYPTO_Finalize();
    return 0;
}