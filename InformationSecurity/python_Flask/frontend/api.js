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
async function apiRegister(username, password, passwordConfirm, email) {
    return await request("/register", {
        method: "POST",
        body: JSON.stringify({
            username,
            password,
            passwordConfirm,
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





// ==================== 隐私求交 API ====================

// 创建隐私求交小组
async function apiCreatePSIGroup(groupName, standardizeMode = 'auto') {
    return await request("/psi-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName, standardizeMode }),
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

// 2026-07-02:PSI 下载“运算结果”(按上传格式 .json/.csv/.txt)
function apiPSIDownloadResultWithOriginalUrl(groupId) {
    return `${API_BASE_URL}/psi-group/${groupId}/download-result-with-original`;
}

// 2026-07-02:PSU 下载“运算结果”(按上传格式 .json/.csv/.txt)
function apiPSUDownloadResultWithOriginalUrl(groupId) {
    return `${API_BASE_URL}/psi-union-group/${groupId}/download-result-with-original`;
}

// 2026-07-02:PSIMatch 下载“运算结果”(按上传格式 .json/.csv/.txt)
function apiPSIMatchDownloadResultWithOriginalUrl(groupId) {
    return `${API_BASE_URL}/psi-match-group/${groupId}/download-result-with-original`;
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
// 2026-07-02 两阶段 JSON path 上传 - 阶段 1 探测
async function apiPSIProbe(groupId, file) {
    const token = sessionStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    try {
        const response = await fetch(`${API_BASE_URL}/psi-group/upload?probe=true`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData,
        });
        const data = await response.json();
        if (response.ok) {
            return { success: true, data };
        }
        return { success: false, message: data.error || "探测失败" };
    } catch (error) {
        console.error("PSI 探测错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

async function apiPSUUnionProbe(groupId, file) {
    const token = sessionStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    try {
        const response = await fetch(`${API_BASE_URL}/psi-union-group/upload?probe=true`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData,
        });
        const data = await response.json();
        if (response.ok) {
            return { success: true, data };
        }
        return { success: false, message: data.error || "探测失败" };
    } catch (error) {
        console.error("PSU 探测错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

async function apiPSIMatchProbe(groupId, file) {
    const token = sessionStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    try {
        const response = await fetch(`${API_BASE_URL}/psi-match-group/upload?probe=true`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData,
        });
        const data = await response.json();
        if (response.ok) {
            return { success: true, data };
        }
        return { success: false, message: data.error || "探测失败" };
    } catch (error) {
        console.error("PSIMatch 探测错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

async function apiPSIUpload(groupId, file, path = "") {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    if (path && path.trim()) {
        formData.append("path", path.trim());
    }

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
async function apiCreatePSIMatchGroup(groupName, standardizeMode = 'auto') {
    return await request("/psi-match-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName, standardizeMode }),
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
async function apiPSIMatchUpload(groupId, file, path = "") {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    if (path && path.trim()) {
        formData.append("path", path.trim());
    }

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
async function apiCreatePSIUnionGroup(groupName, standardizeMode = 'auto') {
    return await request("/psi-union-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName, standardizeMode }),
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
async function apiPSIUnionUpload(groupId, file, path = "") {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    if (path && path.trim()) {
        formData.append("path", path.trim());
    }

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
// ============================================================
// 多轮历史记录 API(2026-07-01:隐私求交小组)
// ============================================================

// 保存当前轮次到历史(receiver = creator 才能调)
async function apiFinalizePSIRound(groupId) {
    return await request(`/psi-group/${groupId}/finalize-round`, {
        method: "POST",
    });
}

// 2026-07-02:receiver 手动触发的开始运算(双方上传后,receiver 按此启动 Kunlun 计算)
async function apiStartPSIComputation(groupId) {
    return await request(`/psi-group/${groupId}/start-computation`, {
        method: "POST",
    });
}

// 拉取小组历史记录
async function apiGetPSIGroupHistory(groupId) {
    return await request(`/psi-group/${groupId}/history`, {
        method: "GET",
    });
}

// 下载某 round 的归档文件
// type: my_plaintext | my_oprf | result
function apiDownloadPSIRoundFile(groupId, roundNum, type) {
    const token = sessionStorage.getItem("token");
    if (!token) {
        alert('未登录,请重新登录');
        return;
    }
    const url = `/api/psi-group/${groupId}/round/${roundNum}/download?type=${type}`;
    // 用 fetch + blob 触发下载,带 JWT
    fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(async response => {
        if (!response.ok) {
            const text = await response.text();
            let msg = '下载失败';
            try {
                const d = JSON.parse(text);
                msg = d.error || msg;
            } catch(e) {}
            throw new Error(msg + ' (HTTP ' + response.status + ')');
        }
        return response.blob();
    })
    .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `psi_${groupId}_round${roundNum}_${type}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    })
    .catch(err => {
        alert('下载失败: ' + err.message);
    });
}

// ============================================================
// PSU (隐私求并) 多轮历史 API
// ============================================================

async function apiFinalizePSUUnionRound(groupId) {
    return await request(`/psi-union-group/${groupId}/finalize-round`, {
        method: "POST",
    });
}

// 2026-07-02:PSU receiver 手动触发开始运算
async function apiStartPSUUnionComputation(groupId) {
    return await request(`/psi-union-group/${groupId}/start-computation`, {
        method: "POST",
    });
}

async function apiGetPSUUnionGroupHistory(groupId) {
    return await request(`/psi-union-group/${groupId}/history`, {
        method: "GET",
    });
}

function apiDownloadPSUUnionRoundFile(groupId, roundNum, type) {
    const token = sessionStorage.getItem("token");
    if (!token) { alert('未登录'); return; }
    const url = `/api/psi-union-group/${groupId}/round/${roundNum}/download?type=${type}`;
    fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    .then(async response => {
        if (!response.ok) {
            const text = await response.text();
            let msg = '下载失败';
            try { const d = JSON.parse(text); msg = d.error || msg; } catch(e) {}
            throw new Error(msg + ' (HTTP ' + response.status + ')');
        }
        return response.blob();
    })
    .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `psu_${groupId}_round${roundNum}_${type}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    })
    .catch(err => { alert('下载失败: ' + err.message); });
}

// ============================================================
// PSIMatch (集合匹配) 多轮历史 API
// ============================================================

async function apiFinalizePSIMatchRound(groupId) {
    return await request(`/psi-match-group/${groupId}/finalize-round`, {
        method: "POST",
    });
}

// 2026-07-02:PSIMatch receiver 手动触发开始运算
async function apiStartPSIMatchComputation(groupId) {
    return await request(`/psi-match-group/${groupId}/start-computation`, {
        method: "POST",
    });
}

async function apiGetPSIMatchGroupHistory(groupId) {
    return await request(`/psi-match-group/${groupId}/history`, {
        method: "GET",
    });
}

function apiDownloadPSIMatchRoundFile(groupId, roundNum, type) {
    const token = sessionStorage.getItem("token");
    if (!token) { alert('未登录'); return; }
    const url = `/api/psi-match-group/${groupId}/round/${roundNum}/download?type=${type}`;
    fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    .then(async response => {
        if (!response.ok) {
            const text = await response.text();
            let msg = '下载失败';
            try { const d = JSON.parse(text); msg = d.error || msg; } catch(e) {}
            throw new Error(msg + ' (HTTP ' + response.status + ')');
        }
        return response.blob();
    })
    .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `psimatch_${groupId}_round${roundNum}_${type}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    })
    .catch(err => { alert('下载失败: ' + err.message); });
}

// ============================================================
// PSI-Sum (隐私求和) API -- 2026-07-07 新增
// ============================================================

async function apiCreatePSISumGroup(groupName, standardizeMode = 'auto') {
    return await request("/psi-sum-group/create", {
        method: "POST",
        body: JSON.stringify({ groupName, standardizeMode }),
    });
}

async function apiJoinPSISumGroup(groupId) {
    return await request("/psi-sum-group/join", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

async function apiLeavePSISumGroup(groupId) {
    return await request("/psi-sum-group/leave", {
        method: "POST",
        body: JSON.stringify({ groupId }),
    });
}

async function apiGetPSISumGroup(groupId) {
    return await request(`/psi-sum-group/${groupId}`, { method: "GET" });
}

async function apiDeletePSISumGroup(groupId) {
    return await request(`/psi-sum-group/${groupId}`, { method: "DELETE" });
}

async function apiStartPSISumComputation(groupId) {
    return await request(`/psi-sum-group/${groupId}/start-computation`, {
        method: "POST",
    });
}

async function apiGetMyPSISumGroups() {
    return await request("/my-psi-sum-groups", { method: "GET" });
}

// 上传 PSI-Sum 文件 (set 可选带 valueFile)
// valueFile: 可选 File 对象，与 set 行数必须一致
async function apiPSISumUpload(groupId, file, valueFile = null) {
    const token = sessionStorage.getItem("token");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("groupId", groupId);
    if (valueFile) {
        formData.append("valueFile", valueFile);
    }

    try {
        const response = await fetch(`${API_BASE_URL}/psi-sum-group/upload`, {
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
        console.error("PSI-Sum 文件上传错误:", error);
        return { success: false, message: "网络连接失败" };
    }
}

async function apiDeletePSISumUpload(groupId) {
    return await request(`/psi-sum-group/${groupId}/delete-upload`, {
        method: "POST",
    });
}

