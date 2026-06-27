// ==================== API 配置 ====================
const API_BASE_URL = "/api";

// ==================== 通用请求函数 ====================
async function request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const defaultOptions = {
        headers: {
            "Content-Type": "application/json",
        },
    };

    // 如果有 token，添加到请求头
    const token = sessionStorage.getItem("token");
    if (token) {
        defaultOptions.headers["Authorization"] = `Bearer ${token}`;
    }

    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers,
        },
    };

    try {
        const response = await fetch(url, finalOptions);
        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || data.message || "请求失败" };
        }
    } catch (error) {
        console.error("API 请求错误:", error);
        return { success: false, message: "网络连接失败，请检查后端服务是否启动" };
    }
}

// ==================== 用户注册 ====================
async function apiRegister(username, password, email) {
    return await request("/register", {
        method: "POST",
        body: JSON.stringify({
            username,
            password,
            email: email || undefined,
        }),
    });
}

// ==================== 用户登录 ====================
async function apiLogin(username, password) {
    return await request("/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
    });
}

// ==================== 获取当前用户信息 ====================
async function apiGetCurrentUser() {
    return await request("/me", { method: "GET" });
}

// ==================== 文件上传与排序 ====================
async function apiSortFile(file) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_BASE_URL}/sort-file`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || "文件处理失败" };
        }
    } catch (error) {
        console.error("文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

// ==================== 获取所有用户（管理员） ====================
async function apiGetAllUsers() {
    return await request("/users", { method: "GET" });
}

// ==================== 删除用户（管理员） ====================
async function apiDeleteUser(username) {
    return await request(`/users/${username}`, { method: "DELETE" });
}

// ==================== 退出登录 ====================
function logout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("isAdmin");
    window.location.href = "login_register.html";
}

// ==================== 小组管理 API ====================

// 创建小组
async function apiCreateGroup(groupName) {
    return await request("/group/create", {
        method: "POST",
        body: JSON.stringify({ groupName }),
    });
}

// 加入小组
async function apiJoinGroup(groupId) {
    return await request("/group/join", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 退出小组
async function apiLeaveGroup(groupId) {
    return await request("/group/leave", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 获取小组详情
async function apiGetGroup(groupId) {
    return await request(`/group/${groupId}`, { method: "GET" });
}

// 解散小组
async function apiDeleteGroup(groupId) {
    return await request(`/group/${groupId}`, { method: "DELETE" });
}

// 小组文件上传
async function apiGroupUpload(groupId, file) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);

    try {
        const response = await fetch(`${API_BASE_URL}/group/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || "文件上传失败" };
        }
    } catch (error) {
        console.error("小组文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

// 获取我的小组列表
async function apiGetMyGroups() {
    return await request("/my-groups", { method: "GET" });
}

// 删除普通小组的上传记录（协作排序使用）
async function apiDeleteGroupUpload(groupId) {
    return await request("/group/upload", {
        method: "DELETE",
        body: JSON.stringify({ groupId }),
    });
}

// ==================== 隐私求交 API ====================

// 创建隐私求交小组
async function apiCreatePSIGroup(groupName) {
    return await request("/psi-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName }),
    });
}

// 加入隐私求交小组
async function apiJoinPSIGroup(groupId) {
    return await request("/psi-group/join", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 退出隐私求交小组
async function apiLeavePSIGroup(groupId) {
    return await request("/psi-group/leave", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 获取隐私求交小组详情
async function apiGetPSIGroup(groupId) {
    return await request(`/psi-group/${groupId}`, { method: "GET" });
}

// 解散隐私求交小组
async function apiDeletePSIGroup(groupId) {
    return await request(`/psi-group/${groupId}`, { method: "DELETE" });
}

// 预览 PSI 己方密文前 20
async function apiPSIPreviewCiphertext(groupId) {
    return await request(`/psi-group/${groupId}/preview-ciphertext`, { method: "GET" });
}

// 下载 PSI 结果文件
function apiPSIDownloadResultUrl(groupId) {
    return `${API_BASE_URL}/psi-group/${groupId}/download-result`;
}

// 预览 PSU 己方密文前 20
async function apiPSUPreviewCiphertext(groupId) {
    return await request(`/psi-union-group/${groupId}/preview-ciphertext`, { method: "GET" });
}

// 下载 PSU 结果文件
function apiPSUDownloadResultUrl(groupId) {
    return `${API_BASE_URL}/psi-union-group/${groupId}/download-result`;
}

// 获取我的隐私求交小组列表
async function apiGetMyPSIGroups() {
    return await request("/my-psi-groups", { method: "GET" });
}

// 上传文件到隐私求交小组
async function apiPSIUpload(groupId, file) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);

    try {
        const response = await fetch(`${API_BASE_URL}/psi-group/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || "文件上传失败" };
        }
    } catch (error) {
        console.error("隐私求交文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

// 删除用户在隐私求交小组中的上传记录
async function apiDeleteUpload(groupId) {
    return await request(`/psi-group/${groupId}/upload`, {
        method: "DELETE",
    });
}

// ==================== 隐私集合匹配 API ====================

// 创建匹配小组
async function apiCreatePSIMatchGroup(groupName) {
    return await request("/psi-match-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName }),
    });
}

// 加入匹配小组
async function apiJoinPSIMatchGroup(groupId) {
    return await request("/psi-match-group/join", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 退出匹配小组
async function apiLeavePSIMatchGroup(groupId) {
    return await request("/psi-match-group/leave", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 获取匹配小组详情
async function apiGetPSIMatchGroup(groupId) {
    return await request(`/psi-match-group/${groupId}`, { method: "GET" });
}

// 解散匹配小组
async function apiDeletePSIMatchGroup(groupId) {
    return await request(`/psi-match-group/${groupId}`, { method: "DELETE" });
}

// 获取我的匹配小组列表
async function apiGetMyPSIMatchGroups() {
    return await request("/my-psi-match-groups", { method: "GET" });
}

// 上传文件到匹配小组
async function apiPSIMatchUpload(groupId, file) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);

    try {
        const response = await fetch(`${API_BASE_URL}/psi-match-group/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || "文件上传失败" };
        }
    } catch (error) {
        console.error("匹配小组文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

// 删除匹配小组上传记录
async function apiDeletePSIMatchUpload(groupId) {
    return await request(`/psi-match-group/${groupId}/upload`, {
        method: "DELETE",
    });
}

// 预览集合匹配己方密文前 20
async function apiPSIMatchPreviewCiphertext(groupId) {
    return await request(`/psi-match-group/${groupId}/preview-ciphertext`, { method: "GET" });
}

// ==================== 隐私集合求并 API ====================

// 创建求并小组
async function apiCreatePSIUnionGroup(groupName) {
    return await request("/psi-union-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName }),
    });
}

// 加入求并小组
async function apiJoinPSIUnionGroup(groupId) {
    return await request("/psi-union-group/join", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 退出求并小组
async function apiLeavePSIUnionGroup(groupId) {
    return await request("/psi-union-group/leave", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

// 获取求并小组详情
async function apiGetPSIUnionGroup(groupId) {
    return await request(`/psi-union-group/${groupId}`, { method: "GET" });
}

// 解散求并小组
async function apiDeletePSIUnionGroup(groupId) {
    return await request(`/psi-union-group/${groupId}`, { method: "DELETE" });
}

// 获取我的求并小组列表
async function apiGetMyPSIUnionGroups() {
    return await request("/my-psi-union-groups", { method: "GET" });
}

// 上传文件到求并小组
async function apiPSIUnionUpload(groupId, file) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);

    try {
        const response = await fetch(`${API_BASE_URL}/psi-union-group/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            return { success: true, data };
        } else {
            return { success: false, message: data.error || "文件上传失败" };
        }
    } catch (error) {
        console.error("求并小组文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

// 删除求并小组上传记录
async function apiDeletePSIUnionUpload(groupId) {
    return await request(`/psi-union-group/${groupId}/upload`, {
        method: "DELETE",
    });
}