# INFO_SECU 1.0.2 隐私计算系统（精简版）

基于 **精简版 Kunlun** 密码学库的 Web 隐私集合运算演示平台，支持 **5 种协议**：PSI / PSU / PSI-Match / PSI-Sum / SS-PSI。

两个参与方（receiver + sender）各自上传自己的明文集合，后端调用 Kunlun 跑 OPRF 协议，任何一方都拿不到对方独有的明文，只看到协议约定范围内该看到的部分。

> ⚠️ **协议覆盖度**: 前 3 个协议 (PSI/PSU/PSI-Match) **协议计算 + 业务流程全真实**; 后 2 个协议 (PSI-Sum/SS-PSI) **业务流程全真实** (成员加入/上传/状态同步走真实 API + JSON 持久化 + polling), **协议计算结果为 mock** (写死 cardinality/sum/intersection 用于演示)

> 📌 **1.0.2 是从 1.0.1 复制过来的"实验田"**：Kunlun 源码精简 91%（48MB → 4MB），仅保留 demo 必需的源码，详细变更见末尾 [变更日志](#变更日志)。

## 协议一览

| 协议 | 含义 | 输出 | 实现状态 |
| --- | --- | --- | --- |
| PSI | Private Set Intersection | 双方集合的**交集** | ✅ 协议计算 + 业务流程全真 |
| PSU | Private Set Union | 双方集合的**并集** | ✅ 协议计算 + 业务流程全真 |
| PSI-Match | 子集匹配 | 判断一方集合是否**完全包含**另一方 | ✅ 协议计算 + 业务流程全真 |
| PSI-Sum | 隐私求和 | 交集元素关联数值之和 (receiver 视角) | ⚡ 业务流程真 + 计算 mock |
| SS-PSI | 多方隐私求交 (4 方) | 所有参与方的**共同交集** | ⚡ 业务流程真 + 计算 mock |

## 目录结构

```
INFO_SECU_1.0.2/                           # 项目根 (整个目录约 180MB)
├── Kunlun/                                # 精简版 Kunlun 源码 (4MB)
│   ├── crypto/ utility/ include/ netio/    # 基础原语
│   ├── mpc/{psi,pso,rpmt,ot,oprf,okvs,peqt,vole}/   # 协议实现
│   ├── filter/bloom_filter.hpp            # cwprf 用 (仅留这1个文件)
│   ├── config/                             # config.h.in 模板
│   ├── test/                               # demo 主程序 my_*.cpp + 协议 unit test
│   ├── CMakeLists.txt                     # 已精简: 删掉 zkp/pke/signature/adcp/gadget 等 18 个 test
│   └── build/                              # 编译产物 (143MB, 不在精简 4MB 内)
├── InformationSecurity/
│   ├── python_Flask/
│   │   ├── backend/                        # Flask 后端
│   │   │   ├── app.py                      # 主程序 (70+ 个 API)
│   │   │   ├── requirements.txt            # 注意: 漏了 Flask-Limiter, 部署时要补装
│   │   │   ├── start.sh / stop.sh
│   │   │   ├── data/                       # 用户/小组/PSI 数据 (.gitignore 排除)
│   │   │   └── uploads/                    # 协议输入输出文件
│   │   └── frontend/                       # HTML + JS 前端
│   └── test/                               # 协议测试数据
└── README.md
```

## 部署

### 1. Kunlun 库 (已内置, 无需额外 clone)

```bash
cd Kunlun
mkdir -p build && cd build
cmake .. && make -j$(nproc)
```

编译产物：
- **7 个 demo binary**：`my_mqrpmt_psi`、`my_mqrpmt_psi_receiver`、`my_mqrpmt_psi_sender`、`my_mqrpmt_psi_card_receiver`、`my_mqrpmt_psi_card_sender`、`my_mqrpmt_psu_receiver`、`my_mqrpmt_psu_sender`
- 19 个协议 unit test binary (test_*)
- 默认输出到 `Kunlun/build/`，Flask 通过 `Config.KUNLUN_BASE` (写在 `app.py` line 57) 查找

### 2. 后端

```bash
cd InformationSecurity/python_Flask/backend

# (a) 装 python3-venv (Ubuntu/Debian 系统缺这包时 venv 建不起来)
sudo apt install -y python3-venv python3-pip

# (b) 必填: 创建 .env (否则 app.py 启动立刻 RuntimeError)
cp .env.example .env
# 生成 JWT 密钥:
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
# 把上面输出那行复制粘贴到 .env

# (c) 装依赖
python3 -m venv venv
venv/bin/pip install -r requirements.txt
# 注意: requirements.txt 漏了 Flask-Limiter, 1.0.1 时代也没补, 手动装上:
venv/bin/pip install Flask-Limiter

# (d) 启动 (任选一种)
./start.sh                                                  # 默认方式 (端口看 app.py Config.PORT)
export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") && python3 -c "import app; app.app.run(host='0.0.0.0', port=Config.PORT, debug=False, use_reloader=False)"  # 避开 Flask debug reloader 不可靠问题
```

启动后访问：**http://localhost:5003/login.html** (1.0.2 默认端口, Config.PORT 在 `app.py` line 66)

> ⚠️ **端口冲突?** 1.0.1 默认 5002, 1.0.2 默认 **5003** (避免两版本同时跑撞端口)。要换端口改 `backend/app.py` line 66 的 `Config.PORT`。

### 3. 前端

`frontend/` 里的 HTML 已由 Flask 当 static 文件服务, 直接通过上面 URL 访问即可, 不需要单独起 HTTP server。

## 各协议页面

- **PSI 交集**：`frontend/privacy_intersection.html`
- **PSU 并集**：`frontend/privacy_union.html`
- **PSI-Match 子集匹配**：`frontend/psi_match.html`
- **主页 / 小组管理 / PSI 三页 JS**：`frontend/home.html` + `frontend/home-psi-pages.js`

后端 API 列表和详细逻辑见 `backend/app.py` 行内注释 (`# ===== 协议名 =====` 分块, 如 `Kunlun PSI 调用` / `PSI 小组 API` / `PSI-Card 路由 API` / `PSI-Union 路由 API`)。

## 安全注意事项

1. **`JWT_SECRET_KEY` 必须自己生成** (`secrets.token_hex(32)`), 绝不能用占位符
2. `.env` 已在 `.gitignore`, **永远不要 commit**; `.env.example` 不含真值, 可以 commit
3. `backend/data/*.json` 含真实用户密码哈希 (bcrypt) 和 PSI 业务数据, 已被 `.gitignore` 排除
4. `Kunlun/PSO_data/*_data/` 是协议测试用的真实数据, 已排除
5. 生产部署建议用 HTTPS + 反向代理 (nginx), 不要直接暴露 Flask 5003 端口
6. **C++ 端路径硬编码**: `Kunlun/test/my_*.cpp` 第 2 行 `#define KUNLUN_BASE_DIR "/root/projects/INFO_SECU_1.0.2/Kunlun"`, 改项目根目录后必须 sed 全量替换并重编译 7 个 demo binary, 否则 Flask 调 binary 会找不到数据目录

## 路径硬编码清单 (项目里搜不到的坑)

| 位置 | 写死路径 |
|---|---|
| `backend/app.py` line 57 | `Config.KUNLUN_BASE` (Python 端) |
| `Kunlun/test/my_*.cpp` 第 2 行 (7 个文件) | `#define KUNLUN_BASE_DIR` (C++ 端, 不读环境变量, 不读命令行) |

迁移项目时两个地方要一起改, 否则会出"Python 启动 OK, 一算 PSI 就 Cannot open ..."的错误。

## 变更日志

### 1.0.2 (2026-07-05, 从 1.0.1 rsync 复制 + 精简)

**精简 (Kunlun 从 129MB → 4MB 源码 + 143MB 编译产物)**:

| 操作 | 删除内容 | 原因 |
|---|---|---|
| `rm -rf` | `Kunlun/{zkp,commitment,pke,signature,adcp,gadget,docs}/` | 7 个 demo 协议完全用不到的密码学库 |
| `rm -f`  | `Kunlun/filter/cuckoo_filter.hpp` | `cwprf_mqrpmt` / `cwprf_psi` 用 `bloom_filter.hpp` 但不用 cuckoo |
| `CMakeLists.txt` | 删 18 个 `ADD_EXECUTABLE` 块 (test_bloom_filter / test_zkp_* / test_pke_* / test_signature_* / test_adcp / test_range_proof / test_rrpke_mqrpmt 等) | 对应被删目录的 test |

**编译验证**: cmake 配置 0 error, `make -j2` 全 25 个目标编过, demo binary 启动 x25519 加速 + EC 415 初始化正常。

**前端/部署修复**:

1. `home.html` 功能介绍补"隐私求并" (1.0.1 漏写)
2. `home.html` 三处 `(只有 receiver 可以保存)` 提示文字清空 (改成空 span, 保留 id 给 JS 用, 避免 null 异常)
3. `backend/app.py` CRLF → LF (rsync 拷过来是 Windows 行尾, sed 替换不动)
4. `requirements.txt` 补 `Flask-Limiter` 提示 (1.0.1 时代就没装, README 加一行)
5. 端口 5002 → 5003 临时切换 (避免和 1.0.1 撞)
6. `KUNLUN_BASE` 7 个 my_*.cpp 的 `#define KUNLUN_BASE_DIR` 全部从 `INFO_SECU_1.0` 改成 `INFO_SECU_1.0.2`

**清理**:

- 删过时 `backend/README.md` (端口 5000 / Windows 桌面路径 / 错的 API 例子)
- 删 `Kunlun/build/mqRPMTPSI.testcase` (43MB, 单元测试预生成数据, demo 不用)
- 删 `Kunlun/build/mqRPMTPSI.pp` + `CMakeCache.txt` + `CMakeLists.txt.bak` + `__pycache__/`

**体积对比**:

| | 1.0.1 (半残: 只编 8 个 binary) | 1.0.2 (完整: 编全 25 个 binary) |
|---|---|---|
| Kunlun 源码 (不含 build) | ~48MB | **~4MB** ⬇️ 91% |
| Kunlun/build/ | 81MB | 143MB |
| InformationSecurity/ | 89MB | 25MB (venv + 空 data/uploads) |
| **整体** | 222MB | **177MB** |

直接比 222→177 看不出源码精简 (因为 1.0.2 编全了 binary 反大 build), **真正效果是 Kunlun 源码从 48MB → 4MB (省 91%)**。

### 1.0.1 (2026-06-25, 上一版本)

原始版本, Kunlun 完整保留 (129MB 源码 + 81MB build), 路径硬编码到 `INFO_SECU_1.0/Kunlun`。

## License

待定。