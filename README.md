# INFO_SECU 隐私计算系统

基于 Kunlun 密码学库的 Web 隐私集合运算演示平台，支持 **PSI / PSU / PSI-Match** 三种协议。

两个参与方（receiver + sender）各自上传自己的明文集合，后端调用 Kunlun 跑 OPRF 协议，任何一方都拿不到对方独有的明文，只看到协议约定范围内该看到的部分。

## 协议一览

| 协议 | 含义 | 输出 |
| --- | --- | --- |
| PSI | Private Set Intersection | 双方集合的**交集** |
| PSU | Private Set Union | 双方集合的**并集** |
| PSI-Match | 子集匹配 | 判断一方集合是否**完全包含**另一方 |

## 目录结构

```
INFO_SECU/
├── Kunlun/                                # 第三方 C++ 密码学库（未上传，见下）
├── InformationSecurity/
│   ├── python_Flask/
│   │   ├── backend/                       # Flask 后端
│   │   │   ├── app.py                     # 主程序（70+ 个 API）
│   │   │   ├── .env.example               # 环境变量模板
│   │   │   ├── requirements.txt
│   │   │   ├── start.sh / stop.sh
│   │   │   ├── data/                      # 用户/小组/PSI 数据（.gitignore 排除）
│   │   │   └── uploads/                   # 协议输入输出文件
│   │   └── frontend/                      # HTML + JS 前端
│   └── test/                              # 协议测试数据
└── README.md
```

## 部署

### 1. Kunlun 库

Kunlun 是第三方 C++ 密码学库，本仓库 `.gitignore` 排除了它（`Kunlun/.git`）。首次部署需要：

1. 按 Kunlun 官方文档克隆并编译（需要 OpenSSL）
2. 把整个 Kunlun 目录放在仓库根目录，路径在 `backend/app.py` 里硬编码

### 2. 后端

```bash
cd InformationSecurity/python_Flask/backend

# (a) 必填：创建 .env
cp .env.example .env
# 生成 JWT 密钥并填到 .env：
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
```

> ⚠️ 没设 `JWT_SECRET_KEY` 时 `app.py` 启动会立刻报错 `RuntimeError`——这是故意的，**绝不能用占位符**（占位符意味着任何 clone 仓库的人都能伪造任意身份登录）。

```bash
# (b) 装依赖
pip install -r requirements.txt

# (c) 启动
./start.sh
# 等价：source venv/bin/activate && python3 app.py
```

启动后访问：**http://localhost:5002/login.html**

### 3. 前端

frontend/ 目录里的 HTML 已由 Flask 当作 static 文件服务，直接通过上面的 URL 访问即可，不需要单独起 HTTP server。

## 各协议页面

- **PSI 交集**：`frontend/privacy_intersection.html`
- **PSU 并集**：`frontend/privacy_union.html`
- **PSI-Match 子集匹配**：`frontend/psi_match.html`
- **主页 / 小组管理 / PSI 三页 JS**：`frontend/home.html` + `frontend/home-psi-pages.js`

后端 API 列表和详细逻辑见 `backend/app.py` 行内注释。

## 安全注意事项

1. **`JWT_SECRET_KEY` 必须自己生成**（`secrets.token_hex(32)`），绝不能用占位符
2. `.env` 已在 `.gitignore`，**永远不要 commit**；`.env.example` 不含真值，可以 commit
3. `backend/data/*.json` 含真实用户密码哈希（bcrypt）和 PSI 业务数据，已被 `.gitignore` 排除
4. `Kunlun/PSO_data/*_data/` 是协议测试用的真实数据，已排除
5. 生产部署建议用 HTTPS + 反向代理（nginx），不要直接暴露 Flask 5002 端口

## License

待定。