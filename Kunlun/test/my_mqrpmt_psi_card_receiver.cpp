// Kunlun 项目路径常量（项目根目录前缀）
#define KUNLUN_BASE_DIR "/root/projects/INFO_SECU_1.0/Kunlun"
#include "../mpc/pso/mqrpmt_psi_card.hpp"
#include "../crypto/setup.hpp"
#include "../utility/print.hpp"
#include <fstream>
#include <vector>
#include <cmath>
#include <algorithm>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <iostream>
#include <unordered_map>
#include <openssl/sha.h>

// ============================================================================
// 0. 全局配置
// ============================================================================

std::string g_group_id = "";  // 小组ID，由命令行参数传入

// ============================================================================
// 1. 自定义 Block 比较器
// ============================================================================

struct BlockEqual {
    bool operator()(const block& a, const block& b) const {
        const uint64_t* pa = reinterpret_cast<const uint64_t*>(&a);
        const uint64_t* pb = reinterpret_cast<const uint64_t*>(&b);
        return pa[0] == pb[0] && pa[1] == pb[1];
    }
};

std::unordered_map<block, std::string, BlockHash, BlockEqual> block_to_string;

// ============================================================================
// 2. 数据结构
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
    size_t HAMMING_WEIGHT;  // 交集基数（交集大小）
};

// ============================================================================
// 3. 辅助工具函数
// ============================================================================

size_t NextPowerOfTwo(size_t n) {
    if (n == 0) return 1;
    size_t power = 1;
    while (power < n) power <<= 1;
    return power;
}

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
    
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(clean.c_str()), clean.size(), hash);
    block result;
    memcpy(&result, hash, 16);
    return result;
}

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
// 4. 从文件加载数据
// ============================================================================

MyTestCase LoadTestCaseFromFiles() {
    MyTestCase testcase;
    
    // 使用动态 group_id 构建路径
    std::string base_dir = KUNLUN_BASE_DIR "/PSO_data/PSI_card_data";
    std::string group_dir = base_dir + "/group_" + g_group_id;
    
    const std::string sender_file = group_dir + "/sender.txt";
    const std::string receiver_file = group_dir + "/receiver.txt";
    
    std::cout << "[Load] Reading from: " << group_dir << std::endl;
    
    // ---- 读取发送方数据 ----
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
            try {
                block b = MyStringToBlockWithMapping(token);
                testcase.vec_X_original.push_back(b);
            } catch (const std::exception& e) {
                std::cerr << "Warning: Skipping invalid token: " << token << std::endl;
            }
        }
    }
    fin_sender.close();
    
    // ---- 读取接收方数据 ----
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
              << " sender items" << std::endl;
    std::cout << "[Load] Loaded " << testcase.RECEIVER_ITEM_NUM_ORIGINAL 
              << " receiver items" << std::endl;
    std::cout << "[DEBUG] block_to_string size: " << block_to_string.size() << std::endl;
    
    return testcase;
}

// ============================================================================
// 5. 填充到 2 的幂次
// ============================================================================

void PadTestCase(MyTestCase& testcase, uint64_t dummy_seed = 0xDEADBEEF) {
    size_t min_size = 128;
    testcase.SENDER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.SENDER_ITEM_NUM_ORIGINAL), min_size);
    testcase.RECEIVER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.RECEIVER_ITEM_NUM_ORIGINAL), min_size);
    
    block dummy = GenerateDummyBlock(dummy_seed);
    
    testcase.vec_X_padded = testcase.vec_X_original;
    testcase.vec_Y_padded = testcase.vec_Y_original;
    
    testcase.vec_X_padded.resize(testcase.SENDER_ITEM_NUM_PADDED, dummy);
    testcase.vec_Y_padded.resize(testcase.RECEIVER_ITEM_NUM_PADDED, dummy);
    
    std::cout << "[Pad] Sender: " << testcase.SENDER_ITEM_NUM_ORIGINAL 
              << " -> " << testcase.SENDER_ITEM_NUM_PADDED << std::endl;
    std::cout << "[Pad] Receiver: " << testcase.RECEIVER_ITEM_NUM_ORIGINAL 
              << " -> " << testcase.RECEIVER_ITEM_NUM_PADDED << std::endl;
}

// ============================================================================
// 6. 保存结果到文件（PSI-Card 输出交集基数 + 己方 OPRF 密文）
// ============================================================================

void SaveCardResultToFile(size_t cardinality, const std::string& filename) {
    std::ofstream fout(filename);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    // 避免 GCC ofstream << size_t 在某些版本下写入二进制原始字节
    // 改用 std::to_string + fout.write
    std::string line = std::to_string(cardinality) + "\n";
    fout.write(line.data(), line.size());
    fout.close();
    std::cout << "[Save] Saved cardinality " << cardinality << " to " << filename << std::endl;
}

// 保存 OPRF 密文（EC25519Point px，32 字节 → 64 字符 hex，每行一个）
void SaveOPRFCiphertext(const std::string& filename, const std::vector<EC25519Point>& vec) {
    std::ofstream fout(filename, std::ios::binary);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    char hex[3];
    for (size_t i = 0; i < vec.size(); i++) {
        const uint8_t* bytes = vec[i].px;
        for (int j = 0; j < 32; j++) {
            snprintf(hex, sizeof(hex), "%02x", bytes[j]);
            fout.put(hex[0]);
            fout.put(hex[1]);
        }
        fout.put('\n');
    }
    fout.close();
    std::cout << "[Save] Saved " << vec.size() << " OPRF ciphertexts to " << filename << std::endl;
}

// ============================================================================
// 7. 主函数 - RECEIVER 版本（PSI-Card）
// ============================================================================

int main(int argc, char* argv[]) {
    CRYPTO_Initialize();
    
    // 接收 group_id 参数
    if (argc > 1) {
        g_group_id = argv[1];
        std::cout << "[PSI-Card] Group ID: " << g_group_id << std::endl;
    } else {
        std::cerr << "Error: Please provide group_id as argument" << std::endl;
        return 1;
    }
    
    std::cout << "========================================" << std::endl;
    std::cout << "    PSI-Card Receiver" << std::endl;
    std::cout << "========================================" << std::endl;
    
    MyTestCase testcase = LoadTestCaseFromFiles();
    
    if (testcase.SENDER_ITEM_NUM_ORIGINAL == 0 || 
        testcase.RECEIVER_ITEM_NUM_ORIGINAL == 0) {
        std::cerr << "Error: Empty data files!" << std::endl;
        return 1;
    }
    
    PadTestCase(testcase);
    
    size_t computational_security_parameter = 128;
    size_t statistical_security_parameter = 40;
    size_t LOG_SENDER = static_cast<size_t>(std::log2(testcase.SENDER_ITEM_NUM_PADDED));
    size_t LOG_RECEIVER = static_cast<size_t>(std::log2(testcase.RECEIVER_ITEM_NUM_PADDED));
    
    // 使用 mqRPMTPSIcard 命名空间
    mqRPMTPSIcard::PP pp = mqRPMTPSIcard::Setup(
        computational_security_parameter,
        statistical_security_parameter,
        LOG_SENDER,
        LOG_RECEIVER
    );
    
    std::cout << "[PSI-Card] Running as RECEIVER..." << std::endl;
    PrintSplitLine('-');
    
    NetIO server("server", "", 8080);
    std::vector<EC25519Point> vec_Fk1_Y;
    size_t cardinality = mqRPMTPSIcard::Receive(server, pp, testcase.vec_Y_padded, &vec_Fk1_Y);

    // 保存结果到小组目录
    std::string result_file = KUNLUN_BASE_DIR "/PSO_data/PSI_card_data/group_" + g_group_id + "/cardinality.txt";
    SaveCardResultToFile(cardinality, result_file);

    // 保存己方 OPRF 密文（让前端可以展示"密文面板"）
    std::string ciphertext_file = KUNLUN_BASE_DIR "/PSO_data/PSI_card_data/group_" + g_group_id + "/receiver_ciphertext.txt";
    SaveOPRFCiphertext(ciphertext_file, vec_Fk1_Y);
    
    std::cout << "[PSI-Card] Receiver finished." << std::endl;
    std::cout << "[PSI-Card] Intersection cardinality: " << cardinality << std::endl;
    PrintSplitLine('-');
    
    CRYPTO_Finalize();
    return 0;
}