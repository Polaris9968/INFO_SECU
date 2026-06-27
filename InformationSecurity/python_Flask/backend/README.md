# Flask Web 应用后端使用说明

## 项目结构

```
backend/
├── app.py          # 主程序
├── users.json      # 用户数据（自动生成）
├── uploads/        # 临时上传文件夹
└── requirements.txt
```

## 安装步骤

### 1. 安装 Python 依赖

在 `backend` 目录下执行：

```bash
cd backend
pip install -r requirements.txt
```

或者单独安装：

```bash
pip install Flask Flask-CORS bcrypt PyJWT Werkzeug
```

### 2. 启动服务器

```bash
python app.py
```

启动成功后会显示：

```
==================================================
🚀 Flask 服务器启动中...
==================================================
📁 静态文件目录: D:\html_css_js\my_first_html
📁 上传文件目录: D:\html_css_js\backend\uploads
📄 用户数据文件: D:\html_css_js\backend\users.json
==================================================
🌐 访问地址: http://localhost:5000/login.html
==================================================
```

### 3. 访问应用

在浏览器打开：http://localhost:5000/login.html

## API 接口说明

### 1. 用户注册

```
POST /api/register
Content-Type: application/json

请求体：
{
    "username": "testuser",
    "password": "123456",
    "email": "test@example.com"
}

响应：
{
    "message": "注册成功",
    "username": "testuser"
}
```

### 2. 用户登录

```
POST /api/login
Content-Type: application/json

请求体：
{
    "username": "testuser",
    "password": "123456"
}

响应：
{
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "username": "testuser",
    "is_admin": false
}
```

### 3. 获取当前用户信息

```
GET /api/me
Authorization: Bearer <token>

响应：
{
    "username": "testuser",
    "email": "test@example.com",
    "is_admin": false
}
```

### 4. 文件上传与排序

```
POST /api/sort-file
Authorization: Bearer <token>
Content-Type: multipart/form-data

表单字段：file（.txt文件）

响应：
{
    "original": [3, 1, 4, 1, 5],
    "sorted": [5, 4, 3, 1, 1],
    "statistics": {
        "count": 5,
        "min": 1,
        "max": 5,
        "average": 2.8,
        "sum": 14
    }
}
```

### 5. 获取所有用户（管理员）

```
GET /api/users
Authorization: Bearer <token>

响应：
{
    "users": [
        {
            "username": "testuser",
            "email": "test@example.com",
            "created_at": "2025-01-01 12:00:00"
        }
    ]
}
```

### 6. 删除用户（管理员）

```
DELETE /api/users/<username>
Authorization: Bearer <token>

响应：
{
    "message": "用户 testuser 已删除"
}
```

## 前端调用示例

```javascript
// 登录
async function login(username, password) {
    const response = await fetch('http://localhost:5000/api/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    if (response.ok) {
        localStorage.setItem('token', data.token);
        localStorage.setItem('username', data.username);
    }
    return data;
}

// 上传文件并排序
async function sortFile(file) {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('http://localhost:5000/api/sort-file', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });
    return await response.json();
}
```

## 支持的数字格式

- 整数：`123`
- 小数：`123.45`
- 负数：`-123`
- 分隔符：空格、换行、逗号

示例文件内容：
```
1 2 3
4.5 -6.7
8,9
```

## 注意事项

1. 生产环境请修改 `JWT_SECRET_KEY`
2. 用户数据存储在 `users.json` 文件中
3. 上传的文件处理完成后会自动删除
4. 默认管理员功能需要手动在 `users.json` 中设置 `"is_admin": true`
