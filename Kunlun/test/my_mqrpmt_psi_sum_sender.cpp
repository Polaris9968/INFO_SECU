// Kunlun 项目路径常量（项目根目录前缀）
#define KUNLUN_BASE_DIR "/root/projects/INFO_SECU_1.0.2/Kunlun"
#include "../mpc/pso/mqrpmt_psi_card_sum.hpp"
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
#include <openssl/bn.h>
#include <tuple>

// ============================================================================
// 0. 全局配置
// ============================================================================

std::string g_group_id = "";  // 小组ID，由命令行参数传入

// ============================================================================
// 1. 自定义 Block 比较器 / 字符串映射（与 PSI-Card 同源）
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
    // sender 视角
    std::vector<block> vec_X_original;          // sender 自己的集合
    std::vector<BigInt> vec_value_original;     // sender 每个元素关联的数值（与 vec_X 一一对应）
    // receiver 视角（sender 启动时也要能读到 receiver 自己的集合做协议 fallback 用不上，但留作一致性）
    std::vector<block> vec_Y_original;
    size_t SENDER_ITEM_NUM_ORIGINAL;
    size_t RECEIVER_ITEM_NUM_ORIGINAL;
    // padded（喂给 OPRF）
    std::vector<block> vec_X_padded;
    std::vector<block> vec_Y_padded;
    std::vector<BigInt> vec_value_padded;
    size_t SENDER_ITEM_NUM_PADDED;
    size_t RECEIVER_ITEM_NUM_PADDED;
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

BigInt StringToBigInt(const std::string& s) {
    std::string clean = s;
    clean.erase(0, clean.find_first_not_of(" \t\n\r,"));
    clean.erase(clean.find_last_not_of(" \t\n\r,") + 1);
    if (clean.empty()) return bn_0;
    BIGNUM* bn = nullptr;
    BN_dec2bn(&bn, clean.c_str());  // 函数本身不报错，失败时 *bn = nullptr
    if (bn == nullptr) {
        std::cerr << "Warning: invalid BigInt token '" << s
                  << "' - defaulting to 0" << std::endl;
        return bn_0;
    }
    BigInt result(bn);  // copy BIGNUM
    BN_free(bn);
    return result;
}

std::string BigIntToString(const BigInt& v) {
    char* s = BN_bn2dec(v.bn_ptr);
    if (s == nullptr) return "0";
    std::string out(s);
    OPENSSL_free(s);
    return out;
}

// ============================================================================
// 4. 从文件加载数据
// ============================================================================

MyTestCase LoadTestCaseFromFiles() {
    MyTestCase testcase;

    std::string base_dir = KUNLUN_BASE_DIR "/PSO_data/PSI_sum_data";
    std::string group_dir = base_dir + "/group_" + g_group_id;

    // sender 集合 + sender value
    const std::string sender_file = group_dir + "/sender.txt";
    const std::string sender_value_file = group_dir + "/sender_value.txt";
    // receiver 集合
    const std::string receiver_file = group_dir + "/receiver.txt";

    std::cout << "[Load] Reading from: " << group_dir << std::endl;

    // ---- 读取 sender 集合 ----
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

    // ---- 读取 sender value ----
    std::ifstream fin_value(sender_value_file);
    if (!fin_value) {
        std::cerr << "Error: Cannot open " << sender_value_file << std::endl;
        exit(1);
    }

    while (std::getline(fin_value, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream iss(line);
        std::string token;
        while (iss >> token) {
            token.erase(std::remove(token.begin(), token.end(), ','), token.end());
            if (token.empty()) continue;
            testcase.vec_value_original.push_back(StringToBigInt(token));
        }
    }
    fin_value.close();

    if (testcase.vec_X_original.size() != testcase.vec_value_original.size()) {
        std::cerr << "Error: sender.txt (" << testcase.vec_X_original.size()
                  << " items) and sender_value.txt ("
                  << testcase.vec_value_original.size()
                  << " items) count mismatch" << std::endl;
        exit(1);
    }

    // ---- 读取 receiver 集合（仅检查非空，不参与 sender 的 OPRF 计算） ----
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
    std::cout << "[Load] Loaded " << testcase.vec_value_original.size()
              << " sender values" << std::endl;

    return testcase;
}

// ============================================================================
// 5. 填充到 2 的幂次
// ============================================================================

void PadTestCase(MyTestCase& testcase, uint64_t dummy_seed = 0xCAFEBABE) {
    size_t min_size = 128;
    testcase.SENDER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.SENDER_ITEM_NUM_ORIGINAL), min_size);
    testcase.RECEIVER_ITEM_NUM_PADDED = std::max(NextPowerOfTwo(testcase.RECEIVER_ITEM_NUM_ORIGINAL), min_size);

    block dummy = GenerateDummyBlock(dummy_seed);

    testcase.vec_X_padded = testcase.vec_X_original;
    testcase.vec_Y_padded = testcase.vec_Y_original;
    testcase.vec_value_padded = testcase.vec_value_original;

    testcase.vec_X_padded.resize(testcase.SENDER_ITEM_NUM_PADDED, dummy);
    testcase.vec_Y_padded.resize(testcase.RECEIVER_ITEM_NUM_PADDED, dummy);
    testcase.vec_value_padded.resize(testcase.SENDER_ITEM_NUM_PADDED, bn_0);

    std::cout << "[Pad] Sender: " << testcase.SENDER_ITEM_NUM_ORIGINAL
              << " -> " << testcase.SENDER_ITEM_NUM_PADDED << std::endl;
    std::cout << "[Pad] Receiver: " << testcase.RECEIVER_ITEM_NUM_ORIGINAL
              << " -> " << testcase.RECEIVER_ITEM_NUM_PADDED << std::endl;
}

// ============================================================================
// 6. 保存结果到文件
// ============================================================================

// cardinality: 整数，避免 GCC ofstream << size_t 在某些版本下写入二进制原始字节
void SaveCardinality(size_t cardinality, const std::string& filename) {
    std::ofstream fout(filename, std::ios::binary);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    std::string line = std::to_string(cardinality) + "\n";
    fout.write(line.data(), line.size());
    fout.close();
    std::cout << "[Save] Saved cardinality " << cardinality
              << " to " << filename << std::endl;
}

// sum: BigInt → 直接用 fout.write 序列化（Kunlun 自带 operator<< 已有二进制 bug 风险）
void SaveSum(const BigInt& sum, const std::string& filename) {
    std::ofstream fout(filename, std::ios::binary);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    std::string s = BigIntToString(sum) + "\n";
    fout.write(s.data(), s.size());
    fout.close();
    std::cout << "[Save] Saved sum " << s << "to " << filename << std::endl;
}

void SaveSenderResult(const std::string& filename) {
    std::ofstream fout(filename);
    if (!fout) {
        std::cerr << "Error: Cannot open " << filename << std::endl;
        return;
    }
    fout << "PSI-Sum Sender finished successfully." << std::endl;
    fout.close();
    std::cout << "[Save] Sender completed." << std::endl;
}

// OPRF 密文（PSI-Card 同款）
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
    std::cout << "[Save] Saved " << vec.size() << " OPRF ciphertexts to "
              << filename << std::endl;
}

// ============================================================================
// 7. 主函数 - SENDER 版本（PSI-Sum）
// ============================================================================

int main(int argc, char* argv[]) {
    CRYPTO_Initialize();

    if (argc > 1) {
        g_group_id = argv[1];
        std::cout << "[PSI-Sum] Group ID: " << g_group_id << std::endl;
    } else {
        std::cerr << "Error: Please provide group_id as argument" << std::endl;
        return 1;
    }

    std::cout << "========================================" << std::endl;
    std::cout << "    PSI-Sum Sender" << std::endl;
    std::cout << "========================================" << std::endl;

    MyTestCase testcase = LoadTestCaseFromFiles();

    if (testcase.SENDER_ITEM_NUM_ORIGINAL == 0 ||
        testcase.RECEIVER_ITEM_NUM_ORIGINAL == 0 ||
        testcase.vec_value_original.empty()) {
        std::cerr << "Error: Empty data files!" << std::endl;
        return 1;
    }

    PadTestCase(testcase);

    size_t computational_security_parameter = 128;
    size_t statistical_security_parameter = 40;

    // PSI-Sum 要求 LOG_SUM_BOUND 是 8 的倍数，LOG_VALUE_BOUND = LOG_SUM_BOUND - LOG_SENDER
    // 用 32 位 SUM_BOUND 起步
    size_t LOG_SUM_BOUND = 32;
    size_t LOG_SENDER = static_cast<size_t>(std::log2(testcase.SENDER_ITEM_NUM_PADDED));
    size_t LOG_RECEIVER = static_cast<size_t>(std::log2(testcase.RECEIVER_ITEM_NUM_PADDED));
    size_t LOG_VALUE_BOUND = LOG_SUM_BOUND - LOG_SENDER;
    if (LOG_VALUE_BOUND <= 0) LOG_VALUE_BOUND = 8;

    mqRPMTPSIcardsum::PP pp = mqRPMTPSIcardsum::Setup(
        computational_security_parameter,
        statistical_security_parameter,
        LOG_SENDER,
        LOG_RECEIVER,
        LOG_SUM_BOUND,
        LOG_VALUE_BOUND
    );

    std::cout << "[PSI-Sum] Running as SENDER..." << std::endl;
    PrintSplitLine('-');

    // PSI-Sum 的 sender 是 server (监听 8080)，等 receiver 连过来
    NetIO server("server", "", 8080);

    size_t cardinality;
    BigInt sum;

    std::tie(cardinality, sum) = mqRPMTPSIcardsum::Send(
        server, pp,
        testcase.vec_X_padded,
        testcase.vec_value_padded
    );

    std::cout << "INTERSECTION CARDINALITY = " << cardinality << std::endl;
    sum.PrintInDec("INTERSECTION SUM");

    std::string group_dir = std::string(KUNLUN_BASE_DIR) + "/PSO_data/PSI_sum_data/group_" + g_group_id;

    // cardinality
    SaveCardinality(cardinality, group_dir + "/sender_cardinality.txt");
    // sum（协议层面只有 sender 拿到 sum，但为了让前端"双方对称可见"，我们冗余写一份给 receiver）
    SaveSum(sum, group_dir + "/sum.txt");
    SaveSenderResult(group_dir + "/sender_result.txt");

    std::cout << "[PSI-Sum] Sender finished." << std::endl;
    PrintSplitLine('-');

    CRYPTO_Finalize();
    return 0;
}
